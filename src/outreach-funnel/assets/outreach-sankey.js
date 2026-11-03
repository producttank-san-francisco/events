// Draws the outreach funnel as a vertical Sankey from the JSON in #funnel-data.
// Needs d3 7 and d3-sankey 0.12 loaded first. Plain browser JS, no build step.
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("funnel-data").textContent);
  const svg = d3.select("#funnel-chart");
  const tip = d3.select("#funnel-tip");
  const number = d3.format(",");

  // Positions in viewBox units, taken from the approved sketch.
  const INK = "#262421";
  const GRAY = "#827d71";
  const NODE = 16; // node bar thickness
  const TOP = 250; // top of the first row; the rows sit at 250, 525 and 800
  const BOTTOM = 816; // bottom of the last row
  const LEFT = 150; // the top row spans LEFT to RIGHT
  const RIGHT = 943;
  const PADDING = 25; // d3-sankey's gap; the top row's real gaps (58 + 3 × 14) add up to the same 4 × 25
  const GAP = 14; // between neighbor nodes
  const ROW_START = [LEFT, 200, 160]; // left edge of each row's first node
  const GAP_BEFORE = { Declined: 64, "No reply yet": 45, "Waiting for host": 70, "Host declined": 141 };
  const LABEL_GAP = 12; // least clear space between two labels in a row
  const STRENGTH = {
    strong: { fill: 0.55, edge: 0.9 },
    mid: { fill: 0.3, edge: 0.6 },
    faint: { fill: 0.1, edge: 0.35 },
  };
  const FULL = { fill: 0.8, edge: 1 };
  const FADED = { fill: 0.05, edge: 0.08 };
  const DRAW_ORDER = { faint: 0, mid: 1, strong: 2 };

  const roles = new Map(data.roles.map((role) => [role.name, role]));
  const people = (count) => `${number(count)} ${count === 1 ? "person" : "people"}`;

  const sankey = d3
    .sankey()
    .nodeId((node) => node.name)
    .nodeAlign(d3.sankeyLeft)
    .nodeSort(null)
    .linkSort(null)
    .nodeWidth(NODE)
    .nodePadding(PADDING)
    // d3-sankey flows left to right: swap the axes here and transpose when drawing
    // (node.x0/x1 is a row's vertical position, node.y0/y1 its horizontal extent).
    .extent([
      [TOP, LEFT],
      [BOTTOM, RIGHT],
    ]);

  function draw() {
    const graph = sankey({
      nodes: data.nodes.map((node) => Object.assign({}, node)),
      links: data.links.map((link) => Object.assign({}, link)),
    });
    const rows = [0, 1, 2].map((depth) => graph.nodes.filter((node) => node.depth === depth));

    const ruler = svg.append("text").attr("visibility", "hidden");
    const width = (text, size) => ruler.attr("font-size", size).text(text).node().getComputedTextLength();
    graph.nodes.forEach((node) => (node.label = label(node, width)));
    ruler.remove();

    placeRow(rows[0], ROW_START[0], () => GAP);
    // Pack the invited roles against the right end; the gap left over sets Via Luma only apart.
    const invited = rows[0].filter((node) => roles.get(node.name).invited !== null);
    const shift = RIGHT - rows[0][rows[0].length - 1].y1;
    if (invited.length < rows[0].length && shift > 0) invited.forEach((node) => move(node, shift));
    placeRow(rows[1], ROW_START[1], (node) => GAP_BEFORE[node.name] || GAP);
    placeRow(rows[2], ROW_START[2], (node) => GAP_BEFORE[node.name] || GAP);
    sankey.update(graph);

    render(graph, invited);
  }

  // A node's label lines and how far they reach past the node's left and right ends (negative: they stop short).
  // Labels sit above, below or left of their row's bars, so only a neighbor's label can collide with them.
  function label(node, width) {
    const span = node.y1 - node.y0;
    let lines;
    let side;
    if (node.depth === 0) {
      const ink = roles.get(node.name).ink;
      const texts = node.lines.length > 1 ? node.lines : wrap(node.lines[0], width, span);
      lines = texts.map((text, i) => ({ text, size: node.lines.length > 1 && i ? 18 : 20, color: ink }));
      side = "above";
    } else {
      const strong = node.targetLinks[0].tier === "strong";
      side = node.sourceLinks.length ? "left" : "below"; // RSVP'd keeps its label on the left, clear of its ribbons
      const [main, sub] = side === "left" ? [26, 18] : [21, 17];
      lines = node.lines.map((text, i) => ({ text, size: i ? sub : main, color: i || !strong ? GRAY : INK }));
    }
    const reach = d3.max(lines, (line) => width(line.text, line.size));
    const over = (reach - span) / 2;
    return side === "left" ? { lines, side, left: reach + GAP, right: 0 } : { lines, side, left: over, right: over };
  }

  // Break a label that is wider than its node into the two lines with the narrowest widest line.
  function wrap(text, width, span) {
    const words = text.split(" ");
    if (width(text, 20) <= span || words.length < 2) return [text];
    let best = null;
    for (let i = 1; i < words.length; i++) {
      const lines = [words.slice(0, i).join(" "), words.slice(i).join(" ")];
      const widest = Math.max(width(lines[0], 20), width(lines[1], 20));
      if (!best || widest < best.widest) best = { lines, widest };
    }
    return best.lines;
  }

  function move(node, dx) {
    node.y0 += dx;
    node.y1 += dx;
  }

  // Lay one row out left to right, wide enough apart that neighbor labels never touch.
  function placeRow(row, start, gapBefore) {
    let x = start;
    row.forEach((node, i) => {
      if (i) x += Math.max(gapBefore(node), row[i - 1].label.right + node.label.left + LABEL_GAP);
      move(node, x - node.y0);
      x = node.y1;
    });
  }

  function ribbonPath(link) {
    const top = link.source.x1;
    const bottom = link.target.x0;
    const middle = (top + bottom) / 2;
    const half = link.width / 2;
    const [s0, s1, t0, t1] = [link.y0 - half, link.y0 + half, link.y1 - half, link.y1 + half];
    return `M${s0},${top}C${s0},${middle} ${t0},${middle} ${t0},${bottom}L${t1},${bottom}C${t1},${middle} ${s1},${middle} ${s1},${top}Z`;
  }

  function text(parent, x, y, words, size, color, anchor) {
    return parent
      .append("text")
      .attr("x", x)
      .attr("y", y)
      .attr("font-size", size)
      .attr("fill", color)
      .attr("text-anchor", anchor || "start")
      .text(words);
  }

  function rule(parent, x0, x1, y, color) {
    parent.append("line").attr("x1", x0).attr("x2", x1).attr("y1", y).attr("y2", y).attr("stroke", color).attr("stroke-width", 1);
  }

  function linkTip(link) {
    const role = roles.get(link.role);
    const fromTop = link.source.depth === 0;
    const from = fromTop ? (role.invited === null ? "not invited" : "invited") : link.source.name;
    const base = fromTop
      ? `${number(role.total)} ${role.invited === null ? "" : "invited "}${role.noun}`
      : `${number(role.rsvped)} RSVP’d ${role.noun}`;
    return { title: `${role.name}: ${from} → ${link.target.name}`, rows: [`${people(link.value)} · ${link.share}% of ${base}`] };
  }

  function nodeTip(node) {
    if (node.depth === 0) {
      const role = roles.get(node.name);
      return {
        title: `${node.name} ${number(node.value)}${role.invited === null ? "" : " invited"}`,
        rows: node.sourceLinks.map((link) => `${link.target.name}: ${number(link.value)}`),
      };
    }
    return {
      title: `${node.name} ${number(node.value)}`,
      rows: node.targetLinks.map((link) => `${link.role}: ${number(link.value)}`),
    };
  }

  function pinnedLine(role) {
    const invited = role.invited === null ? "" : `${number(role.invited)} invited, `;
    return `${role.name}: ${invited}${number(role.rsvped)} RSVP’d, ${number(role.accepted)} accepted`;
  }

  function render(graph, invited) {
    let hover = null; // { link } or { node }
    let pinned = null; // role name
    let pointer = "mouse";

    const header = svg.append("g");
    text(header, 40, 62, data.headline, 36, INK);
    const subline = text(header, 42, 100, data.subline, 19, GRAY);
    rule(header, 40, 1020, 118, GRAY);

    if (invited.length) {
      const x0 = invited[0].y0;
      const x1 = invited[invited.length - 1].y1;
      const bracket = svg.append("g").attr("stroke", INK).attr("stroke-width", 1.4).attr("fill", "none");
      bracket.append("path").attr("d", `M${x0},184V174H${x1}V184`);
      text(svg, (x0 + x1) / 2, 160, `Invited ${number(data.totals.invited)}`, 30, INK, "middle");
    }

    const links = graph.links.slice().sort((a, b) => DRAW_ORDER[a.tier] - DRAW_ORDER[b.tier]);
    const ribbons = svg
      .append("g")
      .selectAll("path")
      .data(links)
      .join("path")
      .attr("class", "ribbon")
      .attr("d", ribbonPath)
      .attr("fill", (link) => roles.get(link.role).color)
      .attr("stroke", (link) => roles.get(link.role).color)
      .attr("stroke-width", 1)
      .attr("tabindex", 0)
      .attr("role", "img")
      .attr("aria-label", (link) => {
        const { title, rows } = linkTip(link);
        return `${title}: ${rows.join(", ")}`;
      });

    const nodes = svg
      .append("g")
      .selectAll("g")
      .data(graph.nodes)
      .join("g")
      .attr("class", "node")
      .attr("tabindex", 0)
      .attr("role", (node) => (node.depth === 0 ? "button" : "img"))
      .attr("aria-label", (node) => {
        const { title, rows } = nodeTip(node);
        return `${title}: ${rows.join(", ")}${node.depth === 0 ? ". Press Enter to pin this role." : ""}`;
      });
    const segments = nodes
      .selectAll("rect.segment")
      .data((node) =>
        node.depth === 0
          ? [{ x0: node.y0, x1: node.y1, y: node.x0, role: node.name }]
          : node.targetLinks.map((link) => ({ x0: link.y1 - link.width / 2, x1: link.y1 + link.width / 2, y: node.x0, role: link.role })),
      )
      .join("rect")
      .attr("class", "segment")
      .attr("x", (segment) => segment.x0)
      .attr("y", (segment) => segment.y)
      .attr("width", (segment) => segment.x1 - segment.x0)
      .attr("height", NODE)
      .attr("fill", (segment) => roles.get(segment.role).color);
    nodes
      .append("rect")
      .attr("x", (node) => node.y0)
      .attr("y", (node) => node.x0)
      .attr("width", (node) => node.y1 - node.y0)
      .attr("height", NODE)
      .attr("fill", "none")
      .attr("stroke", INK)
      .attr("stroke-width", 1);
    nodes
      .append("rect")
      .attr("class", "ring")
      .attr("x", (node) => node.y0 - 4)
      .attr("y", (node) => node.x0 - 4)
      .attr("width", (node) => node.y1 - node.y0 + 8)
      .attr("height", NODE + 8);

    const labels = svg.append("g");
    graph.nodes.forEach((node) => {
      const { lines, side } = node.label;
      const center = (node.y0 + node.y1) / 2;
      lines.forEach((line, i) => {
        if (side === "above") text(labels, center, node.x0 - 10 - (lines.length - 1 - i) * 24, line.text, line.size, line.color, "middle");
        else if (side === "left") text(labels, node.y0 - GAP, node.x0 + 17 + [0, 26, 48][i], line.text, line.size, line.color, "end");
        else text(labels, center, node.x1 + 34 + i * 24, line.text, line.size, line.color, "middle");
      });
    });

    // Role table, bottom right.
    const table = svg.append("g");
    const left = 650;
    const columns = [860, 940, 1020];
    let y = 670;
    text(table, left, y, "Role", 19, GRAY);
    ["Invited", "RSVP’d", "Accepted"].forEach((head, i) => text(table, columns[i], y, head, 19, GRAY, "end"));
    rule(table, left, 1022, y + 8, GRAY);
    const tableRoles = data.table.map((name) => roles.get(name));
    const tableRows = table
      .selectAll("g")
      .data(tableRoles)
      .join("g")
      .attr("class", "table-row")
      .attr("tabindex", 0)
      .attr("role", "button")
      .attr("aria-label", (role) => `${pinnedLine(role)}. Press Enter to pin this role.`);
    tableRows.each(function (role, i) {
      const row = d3.select(this);
      const baseline = y + 27 * (i + 1);
      row.append("rect").attr("class", "ring").attr("x", left - 6).attr("y", baseline - 20).attr("width", 1028 - left).attr("height", 27);
      row.append("rect").attr("x", left - 6).attr("y", baseline - 20).attr("width", 1028 - left).attr("height", 27).attr("fill", "transparent");
      text(row, left, baseline, role.name, 19, role.ink);
      [role.invited === null ? "—" : number(role.invited), number(role.rsvped), number(role.accepted)].forEach((value, j) =>
        text(row, columns[j], baseline, value, 19, INK, "end"),
      );
    });
    y += 27 * tableRoles.length;
    rule(table, left, 1022, y + 9, GRAY);
    y += 28;
    text(table, left, y, "Total", 19, INK);
    [data.totals.invited, data.totals.rsvped, data.totals.accepted].forEach((value, i) => text(table, columns[i], y, number(value), 19, INK, "end"));

    const notes = svg.append("g");
    rule(notes, 40, 1020, 930, GRAY);
    data.notes.forEach((note, i) => text(notes, 40, 958 + 26 * i, note, 17, GRAY));

    function strength(link) {
      if (hover && hover.link) return link === hover.link ? FULL : FADED;
      if (hover && hover.node) return link.source === hover.node || link.target === hover.node ? STRENGTH[link.tier] : FADED;
      if (pinned) return link.role === pinned ? STRENGTH[link.tier] : FADED;
      return STRENGTH[link.tier];
    }

    function refresh() {
      ribbons.style("fill-opacity", (link) => strength(link).fill).style("stroke-opacity", (link) => strength(link).edge);
      segments.style("opacity", (segment) => (!pinned || segment.role === pinned ? 1 : FADED.fill));
      nodes.filter((node) => node.depth === 0).attr("aria-pressed", (node) => String(node.name === pinned));
      tableRows.classed("pinned", (role) => role.name === pinned).attr("aria-pressed", (role) => String(role.name === pinned));
      subline.text(pinned ? pinnedLine(roles.get(pinned)) : data.subline);
    }

    function showTip(content, x, y) {
      tip.selectAll("*").remove();
      tip.append("b").text(content.title);
      content.rows.forEach((row) => tip.append("div").text(row));
      tip.attr("hidden", null);
      placeTip(x, y);
    }

    function placeTip(x, y) {
      const box = tip.node().getBoundingClientRect();
      let left = x + 14;
      let top = y + 14;
      if (left + box.width > window.innerWidth - 8) left = x - box.width - 14;
      if (top + box.height > window.innerHeight - 8) top = y - box.height - 14;
      tip.style("left", `${Math.max(8, left)}px`).style("top", `${Math.max(8, top)}px`);
    }

    function setHover(item, x, y) {
      hover = item;
      refresh();
      showTip(item.link ? linkTip(item.link) : nodeTip(item.node), x, y);
    }

    function clearHover() {
      hover = null;
      tip.attr("hidden", true);
      refresh();
    }

    function togglePin(name) {
      pinned = pinned === name ? null : name;
      refresh();
    }

    // Mouse and pen hover; touch uses taps (below), since a lifted finger "leaves" at once.
    function bindHover(selection, item) {
      selection
        .on("pointerenter", (event, d) => event.pointerType !== "touch" && setHover(item(d), event.clientX, event.clientY))
        .on("pointermove", (event) => event.pointerType !== "touch" && hover && placeTip(event.clientX, event.clientY))
        .on("pointerleave", (event) => event.pointerType !== "touch" && clearHover())
        // Keyboard focus only: a click or tap also focuses, and taps are handled below.
        .on("focus", function (event, d) {
          if (!this.matches(":focus-visible")) return;
          const box = this.getBoundingClientRect();
          setHover(item(d), box.left + box.width / 2, box.top + box.height / 2);
        })
        .on("blur", (event, d) => isHovered(item(d)) && clearHover());
    }
    bindHover(ribbons, (link) => ({ link }));
    bindHover(nodes, (node) => ({ node }));

    const isHovered = (item) => hover && (item.link ? hover.link === item.link : hover.node === item.node);
    // A tap acts as hover; on a role, a second tap pins it.
    function tap(event, item, pinName) {
      event.stopPropagation();
      if (pointer === "touch" && !isHovered(item)) setHover(item, event.clientX, event.clientY);
      else if (pinName) togglePin(pinName);
    }
    ribbons.on("click", (event, link) => tap(event, { link }));
    nodes.on("click", (event, node) => tap(event, { node }, node.depth === 0 ? node.name : null));
    tableRows.on("click", (event, role) => {
      event.stopPropagation();
      togglePin(role.name);
    });

    function pinKeys(selection, name) {
      selection.on("keydown", (event, d) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        togglePin(name(d));
      });
    }
    pinKeys(nodes.filter((node) => node.depth === 0), (node) => node.name);
    pinKeys(tableRows, (role) => role.name);

    svg.on("pointerdown", (event) => (pointer = event.pointerType));
    svg.on("click", () => {
      pinned = null;
      clearHover();
    });
    d3.select(document).on("keydown.funnel", (event) => {
      if (event.key !== "Escape") return;
      pinned = null;
      clearHover();
    });

    refresh();
  }

  const faces = document.fonts ? Promise.all(['20px "et-book"', 'bold 20px "et-book"'].map((face) => document.fonts.load(face))) : Promise.resolve();
  faces.then(draw, draw);
})();
