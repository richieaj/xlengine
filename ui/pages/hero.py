"""Landing hero: the first screen, introducing the IESS 2047 Calculator before
the calculator itself (base.py's <main id="dashboard">) scrolls into view.

Static copy only — nothing here reads model data, so it cannot slow or break
the calculator below it. Substituted into base.py as __HERO_HTML__ by app.py.

Icons are inline SVG (Lucide paths, stroke-only) rather than an icon font:
the project has no icon library, and the page deliberately loads nothing it
does not need (see the font note in base.py).

"Explore the Calculator" is a placeholder href until its destination is
decided; "View Dashboard" scrolls to #dashboard, offset for the sticky header
by the scroll-padding-top that dashboard.js keeps in step with its height.
"""

_ICON = (
    '<svg class="hero-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>'
)

# (title, icon paths, body)
_CARDS = [
    ("What",
     '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M8 6h8"/>'
     '<path d="M16 14v4"/><path d="M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M8 18h.01M12 18h.01"/>',
     "A scenario calculator for India&rsquo;s energy demand and supply. Build a pathway "
     "to 2047 and see the whole energy system it implies."),
    ("Why",
     '<path d="M12 3v18"/><path d="M5 21h14"/><path d="M3 7h18"/>'
     '<path d="M6 7l-3 7a3 3 0 0 0 6 0z"/><path d="M18 7l-3 7a3 3 0 0 0 6 0z"/>',
     "Demand is growing fast. The calculator makes the trade-offs between energy "
     "security, affordability and climate goals visible, measured against India&rsquo;s "
     "commitments: 60% non-fossil power capacity and a 47% cut in emission intensity "
     "by 2035, and net zero by 2070."),
    ("How",
     '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/>'
     '<path d="M1 14h6M9 8h6M17 16h6"/>',
     "Set an ambition level for each demand lever (transport, buildings, industry, "
     "cooking, agriculture) and each supply lever (solar, wind, hydro, nuclear, coal, "
     "oil &amp; gas, bioenergy). See the effect on the energy mix, imports, emissions, "
     "land and cost."),
    ("Who",
     '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
     '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
     "Policymakers, researchers, students, industry and citizens: anyone who wants to "
     "test an idea about India&rsquo;s energy future against the numbers."),
]


def render_hero():
    cards = "".join(
        f'<li class="hero-card">{_ICON.format(icon)}'
        f'<h2 class="hero-card-title">{title}</h2>'
        f'<p class="hero-card-body">{body}</p></li>'
        for title, icon, body in _CARDS
    )
    return f"""
<section class="hero" id="intro" aria-labelledby="hero-title">
  <div class="hero-inner">
    <p class="hero-eyebrow">IESS 2047 Calculator &middot; NITI Aayog</p>
    <h1 class="hero-title" id="hero-title">Explore India&rsquo;s energy future, to 2047</h1>
    <p class="hero-sub">An open-source, interactive &ldquo;what-if&rdquo; tool from NITI Aayog.
      Choose how far India goes on each lever of demand and supply, and see what that
      pathway means for the country&rsquo;s energy, emissions and economy.</p>
    <div class="hero-ctas">
      <a class="hero-btn hero-btn-primary" href="#">Explore the Calculator</a>
      <a class="hero-btn hero-btn-secondary" href="#dashboard">View Dashboard <span aria-hidden="true">&darr;</span></a>
    </div>
    <ul class="hero-cards">{cards}</ul>
  </div>
  <a class="hero-scroll" href="#dashboard" aria-label="Scroll to the dashboard">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
  </a>
</section>
"""
