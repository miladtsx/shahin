document.addEventListener("DOMContentLoaded", () => {
  const availableLangs = {
    en: "en.json",
    fa: "fa.json",
  };
  const translations = {};
  const langButtons = document.querySelectorAll("[data-lang]");
  let currentLang = localStorage.getItem("lang") || "en";

  const fetchTranslations = async () => {
    await Promise.all(
      Object.entries(availableLangs).map(async ([lang, path]) => {
        try {
          const response = await fetch(path);
          if (!response.ok) {
            throw new Error(`Failed to load ${path}`);
          }
          translations[lang] = await response.json();
        } catch (error) {
          console.error(error);
        }
      })
    );
  };

  const getTranslation = (lang, key) => {
    const segments = key.split(".");
    let node = translations[lang];
    for (const segment of segments) {
      if (!node || typeof node !== "object") {
        return null;
      }
      node = node[segment];
    }
    return node;
  };

  const applyTranslations = (lang) => {
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const key = element.getAttribute("data-i18n");
      const value = getTranslation(lang, key);
      if (value) {
        element.innerHTML = value;
      } else {
        console.warn(`Missing translation ${key} for ${lang}`);
      }
    });

    if (lang === "fa") {
      document.body.style.direction = "rtl";
      document.body.style.textAlign = "right";
      document.documentElement.setAttribute("lang", "fa");
    } else {
      document.body.style.direction = "ltr";
      document.body.style.textAlign = "left";
      document.documentElement.setAttribute("lang", "en");
    }
  };

  const persistLanguage = (lang) => {
    currentLang = lang;
    localStorage.setItem("lang", lang);
    applyTranslations(lang);
  };

  langButtons.forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      const lang = event.currentTarget.getAttribute("data-lang");
      if (lang && lang !== currentLang) {
        persistLanguage(lang);
      }
    });
  });

  const init = async () => {
    await fetchTranslations();
    persistLanguage(currentLang);
  };

  init();
});
