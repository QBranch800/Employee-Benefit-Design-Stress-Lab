(() => {
  const canvas = document.getElementById("bsl-ring");
  const model = window.bslRingModel;
  if (!canvas || !model) return;
  if (window.bslRingFrame) cancelAnimationFrame(window.bslRingFrame);

  const context = canvas.getContext("2d");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const dark = canvas.dataset.mode === "dark";
  const period = Number(canvas.dataset.period) * 1000;
  const { tilt, distance, unit, middle } = model.camera;
  const frame = model.frame;
  const steps = 16;

  function tint(patch, colour) {
    if (!dark || patch.kind === "solid") return colour;
    const red = parseInt(colour.slice(1, 3), 16);
    return `rgba(46, 134, 255, ${Math.max(0, 1 - red / 255).toFixed(3)})`;
  }

  function project(radius, angle, level, scale, centreX, centreY) {
    const x = radius * Math.sin(angle);
    const z = radius * Math.cos(angle);
    const y = level * Math.cos(tilt) + z * Math.sin(tilt);
    const depth = z * Math.cos(tilt) - level * Math.sin(tilt);
    const zoom = distance / (distance - depth);
    return [centreX + x * zoom * scale, centreY + y * zoom * scale, depth];
  }

  function outline(patch, turn, scale, centreX, centreY) {
    const upper = [];
    const lower = [];
    let depth = 0;
    for (let step = 0; step <= steps; step += 1) {
      const angle = patch.start + ((patch.end - patch.start) * step) / steps + turn;
      const high = project(patch.radius, angle, patch.top, scale, centreX, centreY);
      const low = project(patch.radius, angle, patch.bottom, scale, centreX, centreY);
      upper.push(high);
      lower.push(low);
      depth += high[2] + low[2];
    }
    return { patch, upper, lower, depth };
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
    const fit = Math.min(width / frame.width, height / frame.height);
    const scale = unit * fit;
    const centreX = width / 2;
    const centreY = height / 2 + (middle - frame.centre) * fit;
    const shapes = model.patches.map((patch) => outline(patch, turn, scale, centreX, centreY));
    shapes.sort((a, b) => a.depth - b.depth);

    for (const shape of shapes) {
      const { patch, upper, lower } = shape;
      const head = upper[steps / 2];
      const foot = lower[steps / 2];
      const fill = context.createLinearGradient(head[0], head[1], foot[0], foot[1]);
      patch.colours.forEach((colour, index) => {
        fill.addColorStop(index / (patch.colours.length - 1), tint(patch, colour));
      });
      context.globalCompositeOperation = patch.kind === "glass" && !dark ? "multiply" : "source-over";
      context.beginPath();
      upper.forEach(([x, y], step) => (step ? context.lineTo(x, y) : context.moveTo(x, y)));
      for (let step = steps; step >= 0; step -= 1) context.lineTo(lower[step][0], lower[step][1]);
      context.closePath();
      context.fillStyle = fill;
      context.fill();
    }
    context.globalCompositeOperation = "source-over";
  }

  let started = null;

  function tick(now) {
    if (!canvas.isConnected) return;
    if (started === null) started = now;
    draw(still ? 0 : (((now - started) % period) / period) * Math.PI * 2);
    if (!still) window.bslRingFrame = requestAnimationFrame(tick);
  }

  window.bslRingFrame = requestAnimationFrame(tick);
})();
