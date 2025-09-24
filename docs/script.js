document.addEventListener('DOMContentLoaded', () => {
    const translations = {
        "en": {
            "nav": {
                "home": "Home",
                "about": "About",
                "demo": "Demo",
                "tech": "Technologies",
                "github": "GitHub",
                "language": "Language"
            },
            "hero": {
                "title": "Advanced Car Plate Tracking System",
                "subtitle": "Leveraging YOLO models for real-time vehicle and license plate detection and recognition.",
                "learn_more": "Learn More"
            },
            "about": {
                "title": "About the Project",
                "paragraph1": "This project is a robust car plate tracking system designed to accurately detect vehicles and their license plates in various scenarios. It utilizes state-of-the-art YOLO (You Only Look Once) models for efficient object detection, followed by character recognition for the extracted license plates.",
                "paragraph2": "Key features include:",
                "feature1": "<strong>Vehicle Detection:</strong> Identifies cars, trucks, and other vehicles in video streams or images.",
                "feature2": "<strong>License Plate Detection:</strong> Precisely locates license plates on detected vehicles.",
                "feature3": "<strong>Character Recognition:</strong> Extracts and recognizes characters from the license plates using a custom-trained classifier.",
                "feature4": "<strong>Tracking:</strong> Implements object tracking to follow vehicles and their plates across multiple frames.",
                "feature5": "<strong>Database Integration:</strong> Stores detected plate information for further analysis."
            },
            "demo": {
                "title": "Live Demo & Screenshots",
                "subtitle": "See the system in action with these examples of vehicle and plate detection.",
                "card1_title": "License Plate Detection",
                "card1_text": "Example of a detected vehicle and its license plate highlighted by the system.",
                "card2_title": "Character Recognition",
                "card2_text": "Close-up of a license plate with individual characters recognized by the classifier."
            },
            "tech": {
                "title": "Technologies Used",
                "yolo": "<strong>YOLO (You Only Look Once):</strong> For real-time object detection (vehicles and license plates).",
                "python": "<strong>Python:</strong> Primary programming language for backend logic and model inference.",
                "opencv": "<strong>OpenCV:</strong> For image and video processing tasks.",
                "pytorch_tf": "<strong>PyTorch/TensorFlow:</strong> For training and deploying deep learning models.",
                "sqlite": "<strong>SQLite:</strong> For local database storage of tracking data.",
                "frontend": "<strong>Streamlit/Flask (Frontend):</strong> For building interactive web interfaces (if applicable).",
                "docker": "<strong>Docker:</strong> For containerization and deployment."
            },
            "footer": {
                "copyright": "&copy; 2025 Your Name. All rights reserved.",
                "repo_text": "Project Repository:",
                "repo_link": "GitHub Link"
            }
        },
        "fa": {
            "nav": {
                "home": "خانه",
                "about": "درباره ما",
                "demo": "نمونه کار",
                "tech": "فناوری ها",
                "github": "گیت‌هاب",
                "language": "زبان"
            },
            "hero": {
                "title": "سیستم پیشرفته ردیابی پلاک خودرو",
                "subtitle": "استفاده از مدل‌های YOLO برای تشخیص و شناسایی پلاک خودرو در زمان واقعی.",
                "learn_more": "بیشتر بدانید"
            },
            "about": {
                "title": "درباره پروژه",
                "paragraph1": "این پروژه یک سیستم قدرتمند ردیابی پلاک خودرو است که برای تشخیص دقیق وسایل نقلیه و پلاک‌های آن‌ها در سناریوهای مختلف طراحی شده است. این سیستم از مدل‌های پیشرفته YOLO (You Only Look Once) برای تشخیص کارآمد اشیاء استفاده می‌کند و سپس با استفاده از یک طبقه‌بندی‌کننده سفارشی آموزش‌دیده، کاراکترهای پلاک‌های استخراج شده را شناسایی می‌کند.",
                "paragraph2": "ویژگی‌های کلیدی عبارتند از:",
                "feature1": "<strong>تشخیص خودرو:</strong> شناسایی خودروها، کامیون‌ها و سایر وسایل نقلیه در جریان‌های ویدیویی یا تصاویر.",
                "feature2": "<strong>تشخیص پلاک:</strong> مکان‌یابی دقیق پلاک‌ها بر روی وسایل نقلیه شناسایی شده.",
                "feature3": "<strong>شناسایی کاراکتر:</strong> استخراج و شناسایی کاراکترها از پلاک‌ها با استفاده از یک طبقه‌بندی‌کننده سفارشی آموزش‌دیده.",
                "feature4": "<strong>ردیابی:</strong> پیاده‌سازی ردیابی اشیاء برای دنبال کردن وسایل نقلیه و پلاک‌های آن‌ها در فریم‌های متعدد.",
                "feature5": "<strong>یکپارچه‌سازی پایگاه داده:</strong> ذخیره اطلاعات پلاک‌های شناسایی شده برای تحلیل‌های بیشتر."
            },
            "demo": {
                "title": "دموی زنده و تصاویر",
                "subtitle": "عملکرد سیستم را با این نمونه‌ها از تشخیص خودرو و پلاک مشاهده کنید.",
                "card1_title": "تشخیص پلاک خودرو",
                "card1_text": "نمونه‌ای از یک خودروی شناسایی شده و پلاک آن که توسط سیستم برجسته شده است.",
                "card2_title": "شناسایی کاراکتر",
                "card2_text": "نمای نزدیک از یک پلاک با کاراکترهای جداگانه که توسط طبقه‌بندی‌کننده شناسایی شده‌اند."
            },
            "tech": {
                "title": "فناوری‌های استفاده شده",
                "yolo": "<strong>YOLO (You Only Look Once):</strong> برای تشخیص اشیاء در زمان واقعی (وسایل نقلیه و پلاک‌ها).",
                "python": "<strong>پایتون:</strong> زبان برنامه‌نویسی اصلی برای منطق بک‌اند و استنتاج مدل.",
                "opencv": "<strong>OpenCV:</strong> برای وظایف پردازش تصویر و ویدیو.",
                "pytorch_tf": "<strong>PyTorch/TensorFlow:</strong> برای آموزش و استقرار مدل‌های یادگیری عمیق.",
                "sqlite": "<strong>SQLite:</strong> برای ذخیره‌سازی داده‌های ردیابی در پایگاه داده محلی.",
                "frontend": "<strong>Streamlit/Flask (فرانت‌اند):</strong> برای ساخت رابط‌های وب تعاملی (در صورت لزوم).",
                "docker": "<strong>داکر:</strong> برای کانتینرسازی و استقرار."
            },
            "footer": {
                "copyright": "&copy; 2025 نام شما. تمامی حقوق محفوظ است.",
                "repo_text": "مخزن پروژه:",
                "repo_link": "لینک گیت‌هاب"
            }
        }
    };

    const langButtons = document.querySelectorAll('[data-lang]');
    let currentLang = localStorage.getItem('lang') || 'en';

    const applyTranslations = (lang) => {
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            const [category, subkey] = key.split('.');
            if (translations[lang] && translations[lang][category] && translations[lang][category][subkey]) {
                element.innerHTML = translations[lang][category][subkey];
            } else {
                console.warn(`Translation key not found: ${key} for language ${lang}`);
            }
        });
        // Set text direction based on language
        if (lang === 'fa') {
            document.body.style.direction = 'rtl';
            document.body.style.textAlign = 'right';
            document.documentElement.setAttribute('lang', 'fa');
        } else {
            document.body.style.direction = 'ltr';
            document.body.style.textAlign = 'left';
            document.documentElement.setAttribute('lang', 'en');
        }
    };

    langButtons.forEach(button => {
        button.addEventListener('click', (event) => {
            event.preventDefault();
            currentLang = event.target.getAttribute('data-lang');
            localStorage.setItem('lang', currentLang);
            applyTranslations(currentLang);
        });
    });

    // Apply translations on initial load
    applyTranslations(currentLang);
});