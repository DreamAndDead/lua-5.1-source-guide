// swith theme

var themes = [
    "gruvbox-dark.css",
    "gruvbox-light.css",
    "doom-one-dark.css",
    "doom-one-light.css",
];

var theme_num = themes.length;

var cur_theme = 0;

function switch_theme() {
    var theme = document.getElementById("theme");
    theme.setAttribute("href", themes[cur_theme % theme_num]);
}

function next_theme() {
    cur_theme = cur_theme + theme_num + 1;
    switch_theme();
}

function prev_theme() {
    cur_theme = cur_theme + theme_num - 1;
    switch_theme();
}

function handler(e) {
    if (e.key == "ArrowLeft") {
      prev_theme()
    }
    if (e.key == "ArrowRight") {
      next_theme()
    }
}

document.addEventListener('keydown', handler, false)

