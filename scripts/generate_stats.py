"""Generates the GitHub Stats and Featured Projects cards for the profile README.

Runs inside GitHub Actions with the built-in GITHUB_TOKEN (no Vercel, no rate limits).

Usage: python scripts/generate_stats.py <username> <out_dir>
Env:   GITHUB_TOKEN
       MOCK=1 -> render with sample data (local preview)
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape

USER = sys.argv[1] if len(sys.argv) > 1 else "Mosad11"
OUT = sys.argv[2] if len(sys.argv) > 2 else "dist"

# Featured project cards: repo name -> description used when the repo has none on GitHub
FEATURED = {
    "booky": "Books app built with Clean Architecture",
    "doctor_app": "Doctor app built with Clean Architecture",
    "ecommerce": "E-commerce app built with Flutter",
    "movies": "Movies app built with Flutter",
}

# Platform boilerplate that Flutter generates in android/ ios/ linux/ windows/ web/
EXCLUDED_LANGUAGES = {"C++", "CMake", "C", "HTML", "Ruby", "Objective-C", "Shell", "Batchfile"}

FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
# Tokyo Night palette (matches the streak card theme)
BG = "#1A1B27"
BORDER = "#2A2E45"
TITLE = "#70A5FD"
TEXT = "#38BDAE"
MUTED = "#A9B1D6"
ACCENT = "#BF91F3"
CARD_H = 225  # stats and languages cards share one height so they line up

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    pullRequests { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        description
        stargazerCount
        forkCount
        primaryLanguage { name color }
        languages(first: 15, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
  }
}
"""


def fetch():
    if os.environ.get("MOCK"):
        return {
            "pullRequests": {"totalCount": 14},
            "repositories": {"totalCount": 9, "nodes": [
                {"name": "booky", "description": None, "stargazerCount": 1, "forkCount": 0,
                 "primaryLanguage": {"name": "Dart", "color": "#00B4AB"},
                 "languages": {"edges": [
                     {"size": 900000, "node": {"name": "Dart", "color": "#00B4AB"}},
                     {"size": 60000, "node": {"name": "C++", "color": "#f34b7d"}},
                     {"size": 30000, "node": {"name": "Kotlin", "color": "#A97BFF"}},
                     {"size": 25000, "node": {"name": "Swift", "color": "#F05138"}},
                     {"size": 8000, "node": {"name": "Java", "color": "#b07219"}}]}}]},
            "contributionsCollection": {
                "totalCommitContributions": 312,
                "restrictedContributionsCount": 540,
                "contributionCalendar": {"totalContributions": 860}},
        }
    now = datetime.now(timezone.utc)
    year_ago = now.replace(year=now.year - 1)
    body = json.dumps({"query": QUERY, "variables": {
        "login": USER, "from": year_ago.isoformat(), "to": now.isoformat()}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


def card(width, height, title, inner):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    .t {{ font: 700 18px {FONT}; fill: {TITLE}; }}
    .l {{ font: 500 14px {FONT}; fill: {MUTED}; }}
    .v {{ font: 700 15px {FONT}; fill: {TEXT}; }}
    .row {{ opacity: 0; animation: in .5s ease-out forwards; }}
    @keyframes in {{ from {{ opacity: 0; transform: translateX(-8px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  </style>
  <rect x="0.5" y="0.5" rx="10" width="{width-1}" height="{height-1}" fill="{BG}" stroke="{BORDER}"/>
  <text x="25" y="38" class="t">{escape(title)}</text>
{inner}
</svg>
'''


def stats_svg(u):
    cc = u["contributionsCollection"]
    stars = sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
    rows = [
        ("⚡", "Contributions (last year)",
         fmt(cc["contributionCalendar"]["totalContributions"] + cc["restrictedContributionsCount"])),
        ("📦", "Commits (last year)", fmt(cc["totalCommitContributions"])),
        ("🔀", "Pull requests", fmt(u["pullRequests"]["totalCount"])),
        ("📁", "Public repositories", fmt(u["repositories"]["totalCount"])),
        ("⭐", "Stars earned", fmt(stars)),
    ]
    inner = []
    for i, (icon, label, value) in enumerate(rows):
        y = 75 + i * 30
        inner.append(
            f'  <g class="row" style="animation-delay:{0.15*i:.2f}s">'
            f'<text x="25" y="{y}" class="l">{icon}  {escape(label)}</text>'
            f'<text x="395" y="{y}" class="v" text-anchor="end">{value}</text></g>')
    return card(420, CARD_H, "GitHub Activity", "\n".join(inner))


def languages_svg(u):
    totals = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            if name in EXCLUDED_LANGUAGES:
                continue
            t = totals.setdefault(name, [0, e["node"]["color"] or "#888"])
            t[0] += e["size"]
    langs = sorted(totals.items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(v[0] for _, v in langs) or 1
    bar_w, x = 370, 25
    segs, legend = [], []
    for i, (name, (size, color)) in enumerate(langs):
        w = bar_w * size / total
        segs.append(f'<rect x="{x:.1f}" y="62" width="{max(w, 0.5):.1f}" height="10" fill="{color}"/>')
        x += w
        col, row = i % 2, i // 2
        lx, ly = 25 + col * 190, 112 + row * 38
        legend.append(
            f'  <g class="row" style="animation-delay:{0.6+0.12*i:.2f}s">'
            f'<circle cx="{lx+5}" cy="{ly-5}" r="5" fill="{color}"/>'
            f'<text x="{lx+16}" y="{ly}" class="l"><tspan class="v" style="font-size:14px">{escape(name)}</tspan>  {100*size/total:.1f}%</text></g>')
    inner = (f'  <clipPath id="bar"><rect x="25" y="62" width="{bar_w}" height="10" rx="5"/></clipPath>\n'
             f'  <g clip-path="url(#bar)"><g style="transform-origin:25px 0;animation:grow 1s ease-out forwards">{"".join(segs)}</g></g>\n'
             + "\n".join(legend))
    return card(420, CARD_H, "Most Used Languages", inner)


def wrap(text, limit):
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > limit:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:2]


def project_svg(repo, fallback):
    name = repo.get("name", "")
    desc = repo.get("description") or fallback
    lang = repo.get("primaryLanguage") or {"name": "Dart", "color": "#00B4AB"}
    w, h = 400, 130
    desc_lines = "".join(
        f'<tspan x="25" dy="{0 if i == 0 else 19}">{escape(line)}</tspan>'
        for i, line in enumerate(wrap(desc, 48)))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <style>
    .n {{ font: 700 17px {FONT}; fill: {TITLE}; }}
    .d {{ font: 400 13.5px {FONT}; fill: {MUTED}; }}
    .m {{ font: 500 13px {FONT}; fill: {MUTED}; }}
    .card {{ animation: fade .6s ease-out both; }}
    @keyframes fade {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
  </style>
  <g class="card">
    <rect x="0.5" y="0.5" rx="10" width="{w-1}" height="{h-1}" fill="{BG}" stroke="{BORDER}"/>
    <clipPath id="cc"><rect x="0.5" y="0.5" rx="10" width="{w-1}" height="{h-1}"/></clipPath>
    <rect x="0" y="0" width="4" height="{h}" fill="{ACCENT}" clip-path="url(#cc)"/>
    <g transform="translate(25,22)" fill="{MUTED}">
      <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"/>
    </g>
    <text x="48" y="35" class="n">{escape(name)}</text>
    <text x="25" y="64" class="d">{desc_lines}</text>
    <circle cx="31" cy="108" r="6" fill="{lang["color"] or "#00B4AB"}"/>
    <text x="43" y="112" class="m">{escape(lang["name"])}</text>
    <text x="140" y="112" class="m">★ {repo.get("stargazerCount", 0)}</text>
    <text x="195" y="112" class="m">⑂ {repo.get("forkCount", 0)}</text>
  </g>
</svg>
'''


def main():
    u = fetch()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_svg(u))
    with open(os.path.join(OUT, "languages.svg"), "w", encoding="utf-8") as f:
        f.write(languages_svg(u))
    repos = {r.get("name"): r for r in u["repositories"]["nodes"]}
    for name, fallback in FEATURED.items():
        with open(os.path.join(OUT, f"repo-{name}.svg"), "w", encoding="utf-8") as f:
            f.write(project_svg(repos.get(name, {"name": name}), fallback))
    print("generated stats, languages and project cards")


if __name__ == "__main__":
    main()
