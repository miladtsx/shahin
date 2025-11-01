import cv2
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Sequence

import numpy as np

from src.common_utils.app_logger import get_logger
from src.common_utils.config import Config, MyConfig
from src.common_utils.debug_image import draw_boxes, show
from src.common_utils.resource_path import get_resource_path
from src.common_utils.video_loader import VideoLoader
from src.db.sqlite import DB
from src.detectors.plate_detector import PlateDetector
from src.detectors.vehicle_detector import VehicleDetector
from src.score.score import score_quality
from src.selector.best_frame_selector import BestFrameSelector
from src.tracker.sort.sort import Sort

logger = get_logger("detect", logfile="logs/app.jsonl")


@dataclass
class DetectionComponents:
    vehicle_detector: VehicleDetector
    plate_detector: PlateDetector
    tracker: Sort
    selector: BestFrameSelector


@dataclass
class DetectionRuntimeState:
    frame_skip: int
    rotation_angle: float
    hot_zone_def: Optional[Sequence[Dict[str, float]]]
    car_detection_threshold: Optional[float]
    plate_detection_threshold: Optional[float]
    hot_zone_mask: Optional[np.ndarray] = None
    cached_mask_shape: Optional[Tuple[int, int]] = None
    rotation_cache: Dict[str, Optional[object]] = field(
        default_factory=lambda: {"shape": None, "matrix": None}
    )


@dataclass
class FrameProcessingResult:
    frame: np.ndarray
    roi: np.ndarray
    frame_index: int


def run_plate_detection():
    """Main function that runs continuously, handling video input failures gracefully"""
    conf: MyConfig = Config().config
    db = DB()

    components = initialize_components(conf, db)
    state = build_runtime_state(conf)

    logger.info("Starting continuous plate detection service...")

    try:
        continuous_detection_loop(conf, components, state)
    finally:
        shutdown_plate_detection(components.selector, db)


def initialize_components(conf: MyConfig, db: DB) -> DetectionComponents:
    vehicle_detector = VehicleDetector(
        get_resource_path("res/models/vehicle_detector_yolov11n.pt"),
        [
            1,  # Bicycle
            2,  # car
            3,  # motorcycle
            5,  # bus
            7,  # truck
        ],
    )
    detector_plate = PlateDetector(
        get_resource_path("res/models/license_plate_detector.pt"), ["license_plate"]
    )
    tracker = Sort(max_age=120 * 5, min_hits=5, iou_threshold=0.05)
    selector = BestFrameSelector(
        db,
        score_quality,
        no_improve_patience=conf.get("no_improve_patience", 20),
        track_timeout=conf.get("track_timeout", 15),
    )
    return DetectionComponents(
        vehicle_detector=vehicle_detector,
        plate_detector=detector_plate,
        tracker=tracker,
        selector=selector,
    )


def build_runtime_state(conf: MyConfig) -> DetectionRuntimeState:
    return DetectionRuntimeState(
        frame_skip=max(conf.get("frame_skip", 1), 1),
        rotation_angle=float(conf.get("rotation_angle", 0) or 0),
        hot_zone_def=conf.get("hot_zone"),  # type: ignore
        car_detection_threshold=conf.get("car_detection_threshold"),
        plate_detection_threshold=conf.get("plate_detection_threshold"),
    )


def continuous_detection_loop(
    conf: MyConfig, components: DetectionComponents, state: DetectionRuntimeState
):
    while True:
        try:
            loader = create_video_loader(conf)
            process_video_stream(loader, components, state)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal, stopping gracefully...")
            break
        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            logger.info("Restarting video processing in 1 seconds...")
            time.sleep(1)


def create_video_loader(conf: MyConfig) -> VideoLoader:
    logger.info("Initializing video loader...")
    loader = VideoLoader(
        conf.get("video_path"),
        retry_delay=conf.get("video_retry_delay", 5),
        max_retry_delay=conf.get("video_max_retry_delay", 60),
    )
    logger.info("Starting video processing...")
    return loader


def process_video_stream(
    loader: VideoLoader,
    components: DetectionComponents,
    state: DetectionRuntimeState,
):
    frame_index = 0
    for frame in loader:
        try:
            result, frame_index = process_frame(frame, frame_index, components, state)
            if result is None:
                continue
            # run detector on full frame to keep IDs stable, mask/filter afterwards
            vehicles = detect_vehicles_in_roi(
                result.frame,
                frame_index,
                components.vehicle_detector,
                state.car_detection_threshold,
            )
            vehicles = filter_boxes_by_hot_zone(vehicles, state.hot_zone_mask)
            vehicles = suppress_edge_boxes(vehicles, result.frame.shape)
            if vehicles is None or vehicles.size == 0:
                continue

            tracked_vehicles = track_vehicles(
                vehicles, components.tracker, components.vehicle_detector
            )
            if not tracked_vehicles:
                continue

            display_tracked_vehicles(result.frame, tracked_vehicles)

            active_boxes = get_active_boxes(tracked_vehicles)
            vehicle_crops, crop_meta, active_ids = collect_vehicle_crops(
                tracked_vehicles,
                result.frame,
                components.selector,
                frame_index,
            )

            if vehicle_crops:
                handle_plate_detections(
                    vehicle_crops,
                    crop_meta,
                    components.plate_detector,
                    components.selector,
                    frame_index,
                    result.frame,
                    state.plate_detection_threshold,
                )

            finalize_tracks(components.selector, active_ids, frame_index, active_boxes)
        except Exception as e:
            logger.error(f"Error processing frame {frame_index}: {e}")
            continue


def process_frame(
    frame: Optional[np.ndarray],
    frame_index: int,
    components: DetectionComponents,
    state: DetectionRuntimeState,
) -> Tuple[Optional[FrameProcessingResult], int]:
    # flush outstanding selector errors every frame so they do not accumulate
    components.selector.flush_pending_failures()

    if frame is None:
        logger.warning("Empty frame received from loader")
        return None, frame_index

    frame = apply_rotation_if_needed(frame, state)

    if is_black_frame(frame):
        logger.warning("Black frame detected, camera may be dead")
        return None, frame_index

    frame_index += 1

    if should_skip_frame(frame_index, state.frame_skip):
        return None, frame_index

    # do not mask here; cache the mask for post-detection filtering instead
    prepare_hot_zone_mask(frame, state)
    return (
        FrameProcessingResult(frame=frame, roi=frame, frame_index=frame_index),
        frame_index,
    )


def apply_rotation_if_needed(
    frame: np.ndarray, state: DetectionRuntimeState
) -> np.ndarray:
    if not state.rotation_angle:
        return frame
    return rotate_frame(frame, state.rotation_angle, state.rotation_cache)


def is_black_frame(frame: np.ndarray) -> bool:
    return (not frame.any()) or frame.mean() < 5


def should_skip_frame(frame_index: int, frame_skip: int) -> bool:
    return frame_index % frame_skip != 0


def prepare_hot_zone_mask(frame: np.ndarray, state: DetectionRuntimeState) -> None:
    # rebuild the hot-zone mask only when input resolution changes
    if not state.hot_zone_def:
        state.hot_zone_mask = None
        state.cached_mask_shape = None
        return

    h, w = frame.shape[:2]
    if state.cached_mask_shape != (h, w):
        state.hot_zone_mask = build_hot_zone_mask(state.hot_zone_def, h, w)
        state.cached_mask_shape = (h, w)


def build_hot_zone_mask(
    hot_zone_def: Sequence[Dict[str, float]], height: int, width: int
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    polygon = np.array(
        [(int(p["x"] * width), int(p["y"] * height)) for p in hot_zone_def],
        dtype=np.int32,
    )
    cv2.fillPoly(mask, [polygon], 255)
    return mask


def detect_vehicles_in_roi(
    frame: np.ndarray,
    frame_index: int,
    vehicle_detector: VehicleDetector,
    detection_threshold: Optional[float],
) -> Optional[np.ndarray]:
    try:
        vehicles = vehicle_detector.detect(frame, conf_threshold=detection_threshold)
        return vehicles if vehicles.size != 0 else None
    except Exception as e:
        logger.error(f"Vehicle detection failed at frame {frame_index}: {e}")
        return None


def filter_boxes_by_hot_zone(
    boxes: Optional[np.ndarray], mask: Optional[np.ndarray]
) -> Optional[np.ndarray]:
    if boxes is None or mask is None:
        return boxes
    # keep detections whose centroid lies inside the mask; discard others cheaply
    h, w = mask.shape[:2]
    keep = []
    for box in boxes:
        x1, y1, x2, y2, conf = box
        cx = int(round((x1 + x2) / 2.0))
        cy = int(round((y1 + y2) / 2.0))
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            continue
        if mask[cy, cx] == 0:
            continue
        keep.append(box)

    return np.array(keep, dtype=np.float64) if keep else None


def suppress_edge_boxes(boxes, roi_shape, min_visible=0.6, edge_margin=8):
    if boxes is None:
        return boxes
    # drop boxes that are mostly outside the ROI or hugging frame borders
    h, w = roi_shape[:2]
    keep = []
    for box in boxes:
        x1, y1, x2, y2, conf = box
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        visible_w = min(x2, w) - max(x1, 0)
        visible_h = min(y2, h) - max(y1, 0)
        visible_ratio = (visible_w * visible_h) / (box_w * box_h)
        touches_edge = (
            x1 <= edge_margin
            or y1 <= edge_margin
            or x2 >= w - edge_margin
            or y2 >= h - edge_margin
        )
        if visible_ratio >= min_visible and not touches_edge:
            keep.append(box)
    return np.array(keep, dtype=np.float64) if keep else None


def track_vehicles(
    vehicles: np.ndarray, tracker: Sort, vehicle_detector: VehicleDetector
) -> List[Dict[str, Tuple[int, int, int, int]]]:
    tracked = tracker.update(vehicles)
    if tracked.size == 0:
        return []

    tracked_vehicles = [
        {"id": int(trk[4]), "bbox": tuple(map(int, trk[:4]))} for trk in tracked
    ]
    tracked_vehicles = [vehicle_detector.get_uuid(trk) for trk in tracked_vehicles]
    return [t for t in tracked_vehicles if t]


def display_tracked_vehicles(frame: np.ndarray, tracked_vehicles: List[Dict]):
    show(draw_boxes(frame.copy(), tracked_vehicles), "Vehicle Tracked")


def get_active_boxes(
    tracked_vehicles: List[Dict],
) -> Dict[str, Tuple[int, int, int, int]]:
    return {trk["id"]: trk["bbox"] for trk in tracked_vehicles if trk.get("bbox")}


def collect_vehicle_crops(
    tracked_vehicles: List[Dict],
    frame: np.ndarray,
    selector: BestFrameSelector,
    frame_index: int,
) -> Tuple[List[np.ndarray], List[Dict], Set[str]]:
    vehicle_crops: List[np.ndarray] = []
    crop_meta: List[Dict] = []
    active_ids: Set[str] = set()

    for tracked in tracked_vehicles:
        vehicle_id = tracked.get("id")
        vehicle_bbox = tracked.get("bbox")
        if not vehicle_id or not vehicle_bbox:
            continue

        active_ids.add(vehicle_id)
        selector.mark_seen(vehicle_id, frame_index, frame)

        x1, y1, x2, y2 = vehicle_bbox
        vehicle_crop = frame[y1:y2, x1:x2]
        if vehicle_crop.size == 0:
            continue

        vehicle_crops.append(vehicle_crop)
        crop_meta.append(
            {"id": vehicle_id, "vehicle_bbox": vehicle_bbox, "crop": vehicle_crop}
        )

    return vehicle_crops, crop_meta, active_ids


def handle_plate_detections(
    vehicle_crops: List[np.ndarray],
    crop_meta: List[Dict],
    plate_detector: PlateDetector,
    selector: BestFrameSelector,
    frame_index: int,
    frame: np.ndarray,
    detection_threshold: Optional[float],
):
    plates_batch = plate_detector.detect_batch(
        vehicle_crops, conf_threshold=detection_threshold
    )

    for meta, plates in zip(crop_meta, plates_batch):
        if not plates:
            continue
        process_plate_candidates(meta, plates, selector, frame_index, frame)


def process_plate_candidates(
    meta: Dict,
    plates: List[Dict],
    selector: BestFrameSelector,
    frame_index: int,
    frame: np.ndarray,
):
    for plate in plates:
        try:
            plate_bbox = plate.get("bbox")
            if not plate_bbox:
                continue

            vehicle_crop = meta["crop"]
            px1, py1, px2, py2 = shrink_box(*plate_bbox)
            plate_crop = vehicle_crop[py1:py2, px1:px2]
            if plate_crop.size == 0:
                continue

            selector.update(
                meta["id"],
                plate_crop,
                frame_index,
                full_frame=frame,
                vehicle_bbox=meta["vehicle_bbox"],
            )
        except Exception as e:
            logger.error(f"Error processing plate for vehicle {meta.get('id')}: {e}")
            continue


def finalize_tracks(
    selector: BestFrameSelector,
    active_ids: Set[str],
    frame_index: int,
    active_boxes: Dict[str, Tuple[int, int, int, int]],
):
    to_finalize = selector.to_finalize(
        active_ids, frame_index, active_boxes=active_boxes
    )
    for vehicle_id in to_finalize or []:
        selector.finalize(vehicle_id, frame_index)


def shutdown_plate_detection(selector: BestFrameSelector, db: DB):
    logger.info("Shutting down plate detection service...")
    selector.flush_pending_failures(force=True)
    db.close()
    logger.info("Plate detection service stopped.")


# Shrink box by a fixed margin percentage
def rotate_frame(
    frame: np.ndarray, angle: float, cache: Optional[dict] = None
) -> np.ndarray:
    """Rotate frame around its center, keeping original dimensions. Cache the transform per frame size."""
    if not angle:
        return frame
    if cache is None:
        cache = {}

    (h, w) = frame.shape[:2]
    if cache.get("shape") != (h, w):
        center = (w / 2, h / 2)
        cache["matrix"] = cv2.getRotationMatrix2D(center, angle, 1.0)
        cache["shape"] = (h, w)

    rotation_matrix = cache["matrix"]
    rotated = cv2.warpAffine(
        frame,
        rotation_matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


def shrink_box(x1, y1, x2, y2):
    w = x2 - x1
    h = y2 - y1
    dxl = int(w * 0.14)
    dxr = int(w * 0.06)
    dy = int(h * 0.23)
    return x1 + dxl, y1 + dy, x2 - dxr, y2 - dy
