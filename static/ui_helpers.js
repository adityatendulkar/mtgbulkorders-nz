(function () {
  const TAG_COLOR_PALETTE = [
    { bg: "#fff4f6", border: "#fbc9d7", ink: "#9a4a66", activeBg: "#ffeef3", activeBorder: "#f4b4c8", activeInk: "#8a425b" },
    { bg: "#fff8f2", border: "#f5d2b3", ink: "#8d5a33", activeBg: "#fff1e6", activeBorder: "#eec49e", activeInk: "#7d4f2c" },
    { bg: "#fffbea", border: "#f3e2a9", ink: "#7e6830", activeBg: "#fff7dd", activeBorder: "#ebd38f", activeInk: "#6f5c2b" },
    { bg: "#f3fbf5", border: "#bfe5c8", ink: "#3f6f4c", activeBg: "#eaf8ee", activeBorder: "#a9dcb6", activeInk: "#396546" },
    { bg: "#f2fbfc", border: "#b8e3e8", ink: "#3b6d74", activeBg: "#e9f7f9", activeBorder: "#a3d8df", activeInk: "#355f65" },
    { bg: "#f1f7ff", border: "#bdd3f6", ink: "#3d5f91", activeBg: "#e8f1ff", activeBorder: "#a8c4ef", activeInk: "#365681" },
    { bg: "#f3f4ff", border: "#c7ccf4", ink: "#4d4f89", activeBg: "#eceeff", activeBorder: "#b3b9ee", activeInk: "#44477a" },
    { bg: "#f7f3ff", border: "#d5c4f3", ink: "#6a4f8f", activeBg: "#f1eaff", activeBorder: "#c6afea", activeInk: "#5e467f" },
    { bg: "#fcf4ff", border: "#e4c3ef", ink: "#7f4b88", activeBg: "#f8ecfd", activeBorder: "#d8b0e6", activeInk: "#71427a" },
    { bg: "#fff3f8", border: "#f0c4d7", ink: "#8a4d68", activeBg: "#fdebf4", activeBorder: "#e6b2ca", activeInk: "#7a445c" },
    { bg: "#f8fafc", border: "#d5dde8", ink: "#506073", activeBg: "#f1f5f9", activeBorder: "#c3cedd", activeInk: "#455567" },
    { bg: "#f1fbf9", border: "#bde5dc", ink: "#3f6d64", activeBg: "#e8f8f4", activeBorder: "#a8dbcf", activeInk: "#385f58" },
  ];

  const CITY_LABEL_OVERRIDES = {
    auckland: "Auckland",
    christchurch: "Christchurch",
    dunedin: "Dunedin",
    hamilton: "Hamilton",
    nelson: "Nelson",
    newplymouth: "New Plymouth",
    online: "Online",
    palmerstonnorth: "Palmerston North",
    wellington: "Wellington",
    whanganui: "Whanganui",
    whangarei: "Whangarei",
  };

  const STORE_LABEL_OVERRIDES = {
    badgerssett: "Badger's Sett",
    baydragon: "BayDragon",
    beadnd: "BeaDnD",
    calicokeep: "Calico Keep",
    cardbard: "Card Bard",
    cardcabin: "Card Cabin",
    cardmasters: "Card Masters",
    cardmerchant: "Card Merchant",
    cardmerchantchristchurch: "Card Merchant Christchurch",
    cardmerchantnelson: "Card Merchant Nelson",
    cardmerchanttakapuna: "Card Merchant Takapuna",
    cardmerchantwellington: "Card Merchant Wellington",
    cardmerchantwhangarei: "Card Merchant Whangarei",
    gamingdna: "Gaming DNA",
    goblingames: "Goblin Games",
    hobbylords: "Hobby Lords",
    hobbymaster: "Hobby Master",
    ironknightgaming: "Iron Knight Gaming",
    magicatwillis: "Magic at Willis",
    magicmagpie: "Magic Magpie",
    novagames: "Nova Games",
    nztradingcards: "NZ Trading Cards",
    otakumart: "Otaku Mart",
    shuffleandcut: "Shuffle and Cut",
    spellbound: "Spellbound",
    tcgcollectornz: "TCG Collector NZ",
    threetreemarket: "Three Tree Market",
    valkyriegames: "Valkyrie Games",
    xpgames: "XP Games",
  };

  function toTitleCase(words) {
    return words
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(" ");
  }

  function formatWithOverrides(value, overrides) {
    const raw = String(value || "");
    const key = raw.trim().toLowerCase();
    if (overrides[key]) {
      return overrides[key];
    }
    const words = key.replace(/[^a-z0-9]+/g, " ").split(/\s+/);
    return toTitleCase(words) || raw;
  }

  function formatCityLabel(city) {
    return formatWithOverrides(city, CITY_LABEL_OVERRIDES);
  }

  function formatStoreLabel(store) {
    return formatWithOverrides(store, STORE_LABEL_OVERRIDES);
  }

  window.CardUiHelpers = {
    ...(window.CardUiHelpers || {}),
    tagColorPalette: TAG_COLOR_PALETTE,
    formatCityLabel,
    formatStoreLabel,
  };
})();
