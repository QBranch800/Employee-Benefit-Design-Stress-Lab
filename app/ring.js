(() => {
  const canvas = document.getElementById("bsl-ring");
  const model = window.bslRingModel;
  if (!canvas || !model) return;
  if (window.bslRingFrame) cancelAnimationFrame(window.bslRingFrame);

  const context = canvas.getContext("2d");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const dark = canvas.dataset.mode === "dark";
  const period = Number(canvas.dataset.period) * 1000;
  const degree = Math.PI / 180;
  const tilt = model.camera.tilt * degree;
  const { distance, unit, middle } = model.camera;
  const frame = model.frame;
  const steps = 16;
  const shape = ["span", "radius", "top", "bottom"];

  const rings = model.rings.map((ring) => ({
    kind: ring.kind,
    slots: ring.slots.map((slot) => ({
      ...slot,
      colours: slot.colours.map((colour) =>
        [1, 3, 5].map((at) => parseInt(colour.slice(at, at + 2), 16)),
      ),
    })),
  }));

  function value(slots, index, key) {
    const count = slots.length;
    const slot = slots[((index % count) + count) % count];
    return key === "centre" ? slot.centre + 360 * Math.floor(index / count) : slot[key];
  }

  function glide(slots, index, key, part) {
    const from = value(slots, index, key);
    const to = value(slots, index + 1, key);
    const leave = (to - value(slots, index - 1, key)) / 2;
    const arrive = (value(slots, index + 2, key) - from) / 2;
    const square = part * part;
    const cube = square * part;
    return (
      (2 * cube - 3 * square + 1) * from +
      (cube - 2 * square + part) * leave +
      (3 * square - 2 * cube) * to +
      (cube - square) * arrive
    );
  }

  function planes(turn) {
    const list = [];
    for (const ring of rings) {
      const count = ring.slots.length;
      for (let plane = 0; plane < count; plane += 1) {
        const place = plane + turn * count;
        const index = Math.floor(place);
        const part = place - index;
        const item = { kind: ring.kind, centre: glide(ring.slots, index, "centre", part) };
        for (const key of shape) item[key] = glide(ring.slots, index, key, part);
        const from = ring.slots[index % count].colours;
        const to = ring.slots[(index + 1) % count].colours;
        item.colours = from.map((stop, at) =>
          stop.map((channel, band) => Math.round(channel + (to[at][band] - channel) * part)),
        );
        list.push(item);
      }
    }
    return list;
  }

  function paint(kind, [red, green, blue]) {
    const alpha = 1 - red / 255;
    if (kind === "glass") {
      return dark ? `rgba(46, 134, 255, ${alpha.toFixed(3)})` : `rgb(${red}, ${green}, ${blue})`;
    }
    if (alpha < 0.01) return "rgba(0, 0, 0, 0)";
    const lift = (channel) => Math.round((channel - red) / alpha);
    return `rgba(0, ${lift(green)}, ${lift(blue)}, ${alpha.toFixed(3)})`;
  }

  function project(radius, angle, level, scale, centreX, centreY) {
    const x = radius * Math.sin(angle);
    const z = radius * Math.cos(angle);
    const y = level * Math.cos(tilt) + z * Math.sin(tilt);
    const depth = z * Math.cos(tilt) - level * Math.sin(tilt);
    const zoom = distance / (distance - depth);
    return [centreX + x * zoom * scale, centreY + y * zoom * scale, depth];
  }

  function outline(item, scale, centreX, centreY) {
    const upper = [];
    const lower = [];
    let depth = 0;
    for (let step = 0; step <= steps; step += 1) {
      const angle = (item.centre + item.span * (step / steps - 0.5)) * degree;
      const high = project(item.radius, angle, item.top, scale, centreX, centreY);
      const low = project(item.radius, angle, item.bottom, scale, centreX, centreY);
      upper.push(high);
      lower.push(low);
      depth += high[2] + low[2];
    }
    return { item, upper, lower, depth };
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
    const shapes = planes(turn).map((item) => outline(item, scale, centreX, centreY));
    shapes.sort((a, b) => a.depth - b.depth);

    for (const { item, upper, lower } of shapes) {
      const head = upper[steps / 2];
      const foot = lower[steps / 2];
      const fill = context.createLinearGradient(head[0], head[1], foot[0], foot[1]);
      item.colours.forEach((colour, index) => {
        fill.addColorStop(index / (item.colours.length - 1), paint(item.kind, colour));
      });
      context.globalCompositeOperation = item.kind === "glass" && !dark ? "multiply" : "source-over";
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
    draw(still ? 0 : ((now - started) % period) / period);
    if (!still) window.bslRingFrame = requestAnimationFrame(tick);
  }

  window.bslRingFrame = requestAnimationFrame(tick);
})();
