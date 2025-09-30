#!/bin/sh

# echo "Clearing previous runs..."
# # Clear previous model
# rm -rf ./runs

# # Clear previous augmented dataset
# rm -rf ./res/train
# rm -rf ./res/train_split

# echo "Augmenting new dataset..."
# # Augment new dataset
# python ./scripts/augmentation/dataset_augment.py

# # Split dataset for training and validation
# python ./scripts/train_classifier/data_splitter.py

# echo "Training model..."
# # Train
# python ./scripts/train_classifier/train_classifier.py


echo "Testing model..."
# Test
python ./scripts/classify/test_classifier.py