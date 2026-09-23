// Native SVG: deliberately no package imports, remote scripts, or runtime CDN.
function drawGraph(component) {
  const {parentElement, data, setTriggerValue, key} = component;
  const root = parentElement.querySelector('.mg-graph');
  root.replaceChildren();
  root.style.height = `${data.height || 520}px`;
  const width = root.clientWidth || 800, height = data.height || 520;
  const ns = 'http://www.w3.org/2000/svg';
  const create = (name, attrs = {}, text) => {
    const node = document.createElementNS(ns, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const svg = create('svg', {class: 'mg-canvas', viewBox: `0 0 ${width} ${height}`,
    tabindex: '0', role: 'group', 'aria-label': 'Граф переводов. Tab — выбрать клиента, Enter — открыть досье. Стрелки — сдвиг, плюс и минус — масштаб.'});
  const defs = create('defs');
  // The component key is unique per mounted instance, including shadow roots.
  const arrowId = `moneygraph-arrow-${String(key || 'network').replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const marker = create('marker', {id: arrowId, viewBox: '0 0 10 10', refX: '9', refY: '5',
    markerWidth: '5', markerHeight: '5', orient: 'auto-start-reverse', markerUnits: 'strokeWidth'});
  marker.append(create('path', {d: 'M 0 0 L 10 5 L 0 10 z', fill: '#91A9B5'}));
  defs.append(marker);
  svg.append(defs);
  const viewport = create('g');
  svg.append(viewport);
  root.append(svg);

  const toolbar = document.createElement('div');
  toolbar.className = 'mg-toolbar';
  toolbar.setAttribute('role', 'group');
  toolbar.setAttribute('aria-label', 'Управление графом');
  const tooltip = document.createElement('div');
  tooltip.className = 'mg-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  tooltip.hidden = true;
  const help = document.createElement('div');
  help.className = 'mg-help';
  help.textContent = 'Нажмите на узел — откроется досье. Перетаскивайте фон для сдвига. Обводка — seed; пунктир — граница данных.';
  root.append(toolbar, tooltip, help);

  let scale = 1, panX = 0, panY = 0, drag = null;
  let suppressClick = false;
  const applyTransform = () => viewport.setAttribute('transform', `translate(${panX} ${panY}) scale(${scale})`);
  const zoom = (factor, x = width / 2, y = height / 2) => {
    const next = Math.max(.35, Math.min(5, scale * factor));
    panX = x - (x - panX) * next / scale;
    panY = y - (y - panY) * next / scale;
    scale = next;
    applyTransform();
    tooltip.hidden = true;
  };
  const reset = () => {scale = 1; panX = 0; panY = 0; applyTransform(); tooltip.hidden = true;};
  for (const [label, title, action] of [
    ['+', 'Приблизить', () => zoom(1.25)], ['−', 'Отдалить', () => zoom(.8)], ['Сброс', 'Сбросить вид графа', reset],
  ]) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.title = title;
    button.setAttribute('aria-label', title);
    button.onclick = action;
    toolbar.append(button);
  }
  const point = (event) => {
    const position = svg.createSVGPoint();
    position.x = event.clientX; position.y = event.clientY;
    return position.matrixTransform(svg.getScreenCTM().inverse());
  };
  const showTooltip = (text, event, anchor) => {
    tooltip.textContent = text;
    tooltip.hidden = false;
    const bounds = root.getBoundingClientRect();
    const anchorBounds = anchor && anchor.getBoundingClientRect();
    const x = event ? event.clientX - bounds.left : anchorBounds.x - bounds.x + anchorBounds.width / 2;
    const y = event ? event.clientY - bounds.top : anchorBounds.y - bounds.y;
    tooltip.style.left = `${Math.max(8, Math.min(x + 12, bounds.width - tooltip.offsetWidth - 8))}px`;
    tooltip.style.top = `${Math.max(8, Math.min(y + 12, bounds.height - tooltip.offsetHeight - 8))}px`;
  };
  const hideTooltip = () => {tooltip.hidden = true;};

  const nodes = new Map(data.nodes.map(node => [node.id, {...node, radius: data.layout === 'ego' && data.nodes.length > 7 && !node.focus ? node.radius * .64 : node.radius, px: data.layout === 'ego' ? Math.max(100, Math.min(width - 100, node.x * width)) : node.x * width, py: 40 + node.y * (height - 85)}]));
  if (data.layout === 'ego' && nodes.size > 1 && data.focus) {
    viewport.append(create('text', {x: Math.max(100, width * .19), y: 65, 'text-anchor': 'middle', class: 'mg-lane'}, 'Плательщики'));
    viewport.append(create('text', {x: width * .5, y: 65, 'text-anchor': 'middle', class: 'mg-lane'}, 'Клиент'));
    viewport.append(create('text', {x: Math.min(width - 100, width * .81), y: 65, 'text-anchor': 'middle', class: 'mg-lane'}, 'Получатели'));
  }
  if (!nodes.size) viewport.append(create('text', {x: width / 2, y: height / 2, 'text-anchor': 'middle', class: 'mg-empty'}, 'В этом представлении нет клиентов'));
  const pairs = new Set(data.edges.map(edge => `${edge.source}:${edge.target}`));
  for (const edge of data.edges) {
    const from = nodes.get(edge.source), to = nodes.get(edge.target);
    if (!from || !to) continue;
    let path;
    if (edge.source === edge.target) {
      const r = from.radius;
      path = `M ${from.px-r*.7} ${from.py-r*.7} C ${from.px-55} ${from.py-72} ${from.px+55} ${from.py-72} ${from.px+r*.7} ${from.py-r*.7}`;
    } else {
      const dx = to.px - from.px, dy = to.py - from.py;
      const length = Math.max(1, Math.hypot(dx, dy));
      const reciprocal = pairs.has(`${edge.target}:${edge.source}`);
      const curve = reciprocal ? 25 : 0;
      const mx = (from.px + to.px) / 2 - dy / length * curve;
      const my = (from.py + to.py) / 2 + dx / length * curve;
      const startLength = Math.max(1, Math.hypot(mx - from.px, my - from.py));
      const endLength = Math.max(1, Math.hypot(to.px - mx, to.py - my));
      const x1 = from.px + (mx - from.px) / startLength * (from.radius + 3);
      const y1 = from.py + (my - from.py) / startLength * (from.radius + 3);
      const x2 = to.px - (to.px - mx) / endLength * (to.radius + 5);
      const y2 = to.py - (to.py - my) / endLength * (to.radius + 5);
      path = `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`;
    }
    const line = create('path', {d: path, class: 'mg-edge', 'stroke-width': edge.width,
      'marker-end': `url(#${arrowId})`, 'data-source': edge.source, 'data-target': edge.target});
    line.append(create('title', {}, edge.tooltip));
    line.onpointerenter = event => showTooltip(edge.tooltip, event);
    line.onpointerleave = hideTooltip;
    viewport.append(line);
  }
  for (const node of nodes.values()) {
    const group = create('g', {class: `mg-node${node.focus ? ' is-focus' : ''}`,
      transform: `translate(${node.px} ${node.py})`, tabindex: '0', role: 'button',
      'aria-label': `${node.tooltip}. Открыть досье.`, 'aria-pressed': String(node.focus), 'data-gid': node.id});
    group.append(create('title', {}, node.tooltip));
    group.append(create('circle', {r: node.radius + 7, class: 'focus-ring'}));
    group.append(create('circle', {r: node.radius, fill: node.color,
      stroke: node.seed ? '#18333F' : '#F6F9FA', 'stroke-width': node.seed ? 3 : 1.5}));
    if (node.boundary) group.append(create('circle', {r: node.radius + 3, fill: 'none',
      stroke: '#18333F', 'stroke-width': 1.5, 'stroke-dasharray': '4 3'}));
    const laneLabel = data.layout === 'ego' && !node.focus;
    const left = node.x < .5;
    const labelX = laneLabel ? (left ? -1 : 1) * (node.radius + 8) : 0;
    const visible = node.label_visible && (data.nodes.length <= 20 || node.focus);
    group.append(create('text', {x: labelX, y: laneLabel ? 4 : node.radius + 18,
      'text-anchor': laneLabel ? (left ? 'end' : 'start') : 'middle',
      class: `node-label${visible ? '' : ' hidden-label'}`}, node.label));
    const select = () => {
      if (suppressClick) return;
      hideTooltip();
      setTriggerValue('selected', node.id);
    };
    group.onclick = select;
    group.onkeydown = event => {
      if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); event.stopPropagation(); select();}
    };
    group.onpointerenter = event => showTooltip(node.tooltip, event);
    group.onpointerleave = hideTooltip;
    group.onfocus = () => showTooltip(node.tooltip, null, group);
    group.onblur = hideTooltip;
    viewport.append(group);
  }
  svg.onpointerdown = event => {
    if (event.button !== 0 || event.target.closest('.mg-node')) return;
    const p = point(event);
    suppressClick = false;
    drag = {x: p.x, y: p.y, initialX: panX, initialY: panY};
    svg.setPointerCapture(event.pointerId);
    svg.classList.add('panning');
    hideTooltip();
  };
  svg.onpointermove = event => {
    if (!drag) return;
    const p = point(event);
    panX = drag.initialX + p.x - drag.x;
    panY = drag.initialY + p.y - drag.y;
    if (Math.hypot(p.x - drag.x, p.y - drag.y) > 4) suppressClick = true;
    applyTransform();
  };
  const endDrag = event => {
    drag = null;
    svg.classList.remove('panning');
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
    suppressClick = false;
  };
  svg.onpointerup = endDrag;
  svg.onpointercancel = endDrag;
  svg.onkeydown = event => {
    const actions = {'+': () => zoom(1.25), '=': () => zoom(1.25), '-': () => zoom(.8),
      '0': reset, ArrowLeft: () => {panX += 35;}, ArrowRight: () => {panX -= 35;},
      ArrowUp: () => {panY += 35;}, ArrowDown: () => {panY -= 35;}};
    if (event.key === 'Escape') {hideTooltip(); svg.focus(); return;}
    if (actions[event.key]) {event.preventDefault(); actions[event.key](); applyTransform();}
  };
  // Ctrl-wheel is deliberate so the graph does not capture normal page scroll.
  const wheel = event => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    const p = point(event);
    zoom(event.deltaY < 0 ? 1.12 : 1 / 1.12, p.x, p.y);
  };
  svg.addEventListener('wheel', wheel, {passive: false});
  return () => {
    svg.removeEventListener('wheel', wheel);
    root.replaceChildren();
  };
}

// Rebuild only when the available width changes (sidebar or viewport resize).
// SVG units stay physical pixels, keeping identifiers readable on laptops.
export default function renderGraph(component) {
  const root = component.parentElement.querySelector('.mg-graph');
  let width = root.clientWidth;
  let cleanup = drawGraph(component);
  const observer = new ResizeObserver(() => {
    const next = root.clientWidth;
    if (next && Math.abs(next - width) > 1) {
      width = next;
      cleanup();
      cleanup = drawGraph(component);
    }
  });
  observer.observe(root);
  return () => {observer.disconnect(); cleanup();};
}
