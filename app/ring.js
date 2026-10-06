(() => {
  const canvas = document.getElementById("bsl-ring");
  if (!canvas) return;
  if (window.bslRingFrame) cancelAnimationFrame(window.bslRingFrame);

  const context = canvas.getContext("2d");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const data = canvas.dataset;
  const planes = 7;
  const steps = 14;
  const distance = 4;
  const period = Number(data.period) * 1000;
  const pitch = (Math.PI * 2) / planes;
  const glass = Number(data.glass);
  const rings = [
    { tilt: 0.44, height: 0.64, span: 0.44, offset: 0, solid: true },
    { tilt: 0.7, height: 0.86, span: 0.62, offset: pitch / 2, solid: false },
  ];

  function colours(shape) {
    if (shape.ring.solid) return [data.solidTop, data.solidBottom];
    const strength = glass * (1.25 - 0.7 * ((shape.depth + 1) / 2));
    return [`rgba(${data.pale}, ${strength})`, `rgba(${data.pale}, ${strength * 0.8})`];
  }

  function project(angle, level, tilt, scale, centreX, centreY) {
    const x = Math.sin(angle);
    const z = Math.cos(angle);
    const y = level * Math.cos(tilt) + z * Math.sin(tilt);
    const depth = z * Math.cos(tilt) - level * Math.sin(tilt);
    const zoom = distance / (distance - depth);
    return [centreX + x * zoom * scale, centreY + y * zoom * scale, depth];
  }

  function draw(turn) {
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    const scale = Math.min(width / 2.7, height / 2.5);
    const centreX = width / 2;
    const centreY = height * 0.45;
    const shapes = [];

    for (const ring of rings) {
      for (let index = 0; index < planes; index += 1) {
        const middle = index * pitch + ring.offset + turn;
        const from = middle - ring.span / 2;
        const upper = [];
        const lower = [];
        for (let step = 0; step <= steps; step += 1) {
          const angle = from + (ring.span * step) / steps;
          upper.push(project(angle, -ring.height / 2, ring.tilt, scale, centreX, centreY));
          lower.push(project(angle, ring.height / 2, ring.tilt, scale, centreX, centreY));
        }
        const head = project(middle, -ring.height / 2, ring.tilt, scale, centreX, centreY);
        const foot = project(middle, ring.height / 2, ring.tilt, scale, centreX, centreY);
        shapes.push({ ring, upper, lower, head, foot, depth: (head[2] + foot[2]) / 2 });
      }
    }

    shapes.sort((a, b) => a.depth - b.depth);
    for (const shape of shapes) {
      const fill = context.createLinearGradient(shape.head[0], shape.head[1], shape.foot[0], shape.foot[1]);
      const [top, bottom] = colours(shape);
      fill.addColorStop(0, top);
      fill.addColorStop(1, bottom);
      context.beginPath();
      shape.upper.forEach(([x, y], step) => (step ? context.lineTo(x, y) : context.moveTo(x, y)));
      shape.lower.reverse().forEach(([x, y]) => context.lineTo(x, y));
      context.closePath();
      context.fillStyle = fill;
      context.fill();
    }
  }

  function frame(now) {
    if (!canvas.isConnected) return;
    draw(still ? 0 : ((now % period) / period) * Math.PI * 2);
    if (!still) window.bslRingFrame = requestAnimationFrame(frame);
  }

  window.bslRingFrame = requestAnimationFrame(frame);
})();
