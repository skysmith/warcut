const canvas = document.getElementById("stage");
const ctx = canvas.getContext("2d");
const playButton = document.getElementById("play");
const restartButton = document.getElementById("restart");
const recordButton = document.getElementById("record");
const scrub = document.getElementById("scrub");
const timeLabel = document.getElementById("time");
const shotLabel = document.getElementById("shot");
const beatList = document.getElementById("beat-list");
const download = document.getElementById("download");

const scene = {
  duration: 48,
  title: "Barcelona - July 1936",
  beats: [
    {
      id: "wide",
      label: "opening wide",
      start: 0,
      end: 7,
      copy: "A street waits between official command and local force.",
      caption: "BARCELONA - JULY 1936",
    },
    {
      id: "militia_enters",
      label: "worker militia enters",
      start: 7,
      end: 16,
      copy: "The militia arrives from the factory side of the city.",
      caption: "power moves into the street",
    },
    {
      id: "checkpoint",
      label: "checkpoint forms",
      start: 16,
      end: 27,
      copy: "The old uniform can still give orders, but the street has another answer.",
      caption: "orders from Madrid do not carry the same weight",
    },
    {
      id: "parallel",
      label: "parallel authority",
      start: 27,
      end: 39,
      copy: "The crowd gathers around the armed workers, not the official post.",
      caption: "parallel power has appeared",
    },
    {
      id: "hold",
      label: "final hold",
      start: 39,
      end: 48,
      copy: "The government remains, but it is no longer alone.",
      caption: "one city - multiple authorities",
    },
  ],
  actors: {
    militia: {
      name: "Militia Worker",
      coat: "#5d4637",
      shirt: "#b44a3c",
      trousers: "#272727",
      cap: "#2b2a27",
      accent: "#cfa35b",
    },
    officer: {
      name: "Army Officer",
      coat: "#30424e",
      shirt: "#d7c9aa",
      trousers: "#1d2a31",
      cap: "#233440",
      accent: "#222",
    },
    organizer: {
      name: "Union Organizer",
      coat: "#26372e",
      shirt: "#d0b979",
      trousers: "#202020",
      cap: "#6c2723",
      accent: "#b3362f",
    },
  },
};

const actorPaths = {
  militia: [
    [0, -210, 502],
    [7, -120, 502],
    [16, 448, 502],
    [27, 520, 502],
    [48, 530, 502],
  ],
  officer: [
    [0, 1044, 501],
    [12, 1000, 501],
    [18, 805, 501],
    [27, 820, 501],
    [39, 900, 501],
    [48, 930, 501],
  ],
  organizer: [
    [0, -170, 506],
    [18, -160, 506],
    [27, 368, 506],
    [39, 430, 506],
    [48, 440, 506],
  ],
};

const crowdSeeds = Array.from({ length: 20 }, (_, index) => ({
  x: 155 + index * 44 + Math.sin(index * 2.1) * 14,
  y: 510 + Math.cos(index * 1.6) * 8,
  scale: 0.78 + (index % 5) * 0.045,
  tone: ["#3b3430", "#53392f", "#293641", "#4d3f2c", "#46313a"][index % 5],
}));

let currentTime = 0;
let playing = true;
let lastFrame = performance.now();
let recorder = null;
let recordedChunks = [];

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function smoothstep(value) {
  const t = clamp(value, 0, 1);
  return t * t * (3 - 2 * t);
}

function easeInOut(value) {
  return 0.5 - Math.cos(clamp(value, 0, 1) * Math.PI) / 2;
}

function samplePath(points, time) {
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (time >= a[0] && time <= b[0]) {
      const t = easeInOut((time - a[0]) / (b[0] - a[0]));
      return { x: lerp(a[1], b[1], t), y: lerp(a[2], b[2], t) };
    }
  }
  const point = time < points[0][0] ? points[0] : points[points.length - 1];
  return { x: point[1], y: point[2] };
}

function activeBeat() {
  return scene.beats.find((beat) => currentTime >= beat.start && currentTime < beat.end) ?? scene.beats.at(-1);
}

function cameraState() {
  const checkpoint = smoothstep((currentTime - 14) / 13);
  const finalPush = smoothstep((currentTime - 31) / 12);
  return {
    x: lerp(0, 90, checkpoint) + finalPush * 40,
    y: lerp(0, -14, finalPush),
    zoom: lerp(1, 1.12, checkpoint) + finalPush * 0.08,
  };
}

function drawScene() {
  const beat = activeBeat();
  const camera = cameraState();
  ctx.save();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawBackdrop();

  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.scale(camera.zoom, camera.zoom);
  ctx.translate(-canvas.width / 2 - camera.x, -canvas.height / 2 - camera.y);

  drawStreet();
  drawBuildings();
  drawBarricade();
  drawCrowd();
  drawActor("organizer", scene.actors.organizer, samplePath(actorPaths.organizer, currentTime), -1);
  drawActor("militia", scene.actors.militia, samplePath(actorPaths.militia, currentTime), 1);
  drawActor("officer", scene.actors.officer, samplePath(actorPaths.officer, currentTime), -1);
  drawForeground();
  ctx.restore();

  drawOverlays(beat);
}

function drawBackdrop() {
  const sky = ctx.createLinearGradient(0, 0, 0, 720);
  sky.addColorStop(0, "#9d9a8e");
  sky.addColorStop(0.42, "#c2ad84");
  sky.addColorStop(1, "#33251d");
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, 1280, 720);

  ctx.fillStyle = "rgba(56, 47, 43, 0.28)";
  for (let i = 0; i < 45; i += 1) {
    ctx.fillRect(i * 36 - 20, 0, 10, 720);
  }
}

function drawBuildings() {
  drawBuilding(30, 120, 270, 370, "#6d5642", "#33251f");
  drawBuilding(282, 74, 310, 416, "#796044", "#3a2921");
  drawBuilding(690, 95, 270, 390, "#634d40", "#2d231f");
  drawBuilding(948, 130, 290, 360, "#5d5046", "#28231f");

  ctx.save();
  ctx.translate(470, 170);
  ctx.rotate(-0.05);
  ctx.fillStyle = "#9d302b";
  ctx.fillRect(0, 0, 170, 52);
  ctx.fillStyle = "#e1c36d";
  ctx.fillRect(0, 17, 170, 18);
  ctx.fillStyle = "rgba(0, 0, 0, 0.25)";
  ctx.fillRect(0, 0, 170, 52);
  ctx.restore();
}

function drawBuilding(x, y, w, h, fill, trim) {
  ctx.fillStyle = fill;
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = trim;
  for (let row = 0; row < 3; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      ctx.fillRect(x + 34 + col * 76, y + 48 + row * 82, 36, 48);
    }
  }
  ctx.fillStyle = "rgba(255, 236, 184, 0.16)";
  ctx.fillRect(x + 8, y + 8, w - 16, 8);
}

function drawStreet() {
  ctx.fillStyle = "#352d2a";
  ctx.fillRect(-120, 472, 1520, 260);
  ctx.fillStyle = "rgba(230, 211, 170, 0.14)";
  for (let i = 0; i < 32; i += 1) {
    ctx.fillRect(i * 48 - 80, 585 + Math.sin(i) * 4, 30, 3);
  }
}

function drawBarricade() {
  const build = smoothstep((currentTime - 15) / 12);
  ctx.save();
  ctx.translate(580, 498);
  ctx.globalAlpha = build;
  ctx.fillStyle = "#6d4b31";
  for (let i = 0; i < 5; i += 1) {
    ctx.save();
    ctx.translate(i * 38, i % 2 ? 16 : 0);
    ctx.rotate((i - 2) * 0.06);
    ctx.fillRect(-12, -16, 74, 22);
    ctx.restore();
  }
  ctx.fillStyle = "#2f2d2b";
  ctx.fillRect(42, -34, 96, 26);
  ctx.restore();
}

function drawCrowd() {
  const crowdIn = smoothstep((currentTime - 22) / 14);
  for (const [index, person] of crowdSeeds.entries()) {
    const x = lerp(person.x - 180, person.x + 260, crowdIn);
    const y = person.y + Math.sin(currentTime * 1.8 + index) * 1.6;
    drawSimplePerson(x, y, person.scale, person.tone, crowdIn * 0.74);
  }
}

function drawSimplePerson(x, y, scale, color, alpha) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.translate(x, y);
  ctx.scale(scale, scale);
  ctx.fillStyle = color;
  ctx.fillRect(-11, -38, 22, 38);
  ctx.fillStyle = "#c19a76";
  ctx.beginPath();
  ctx.arc(0, -48, 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawActor(id, palette, pos, facing) {
  const bob = Math.sin(currentTime * 5 + pos.x * 0.02) * 2;
  const gesture = id === "officer"
    ? smoothstep((currentTime - 17) / 2) * (1 - smoothstep((currentTime - 28) / 3))
    : id === "militia"
      ? smoothstep((currentTime - 22) / 2)
      : smoothstep((currentTime - 29) / 3);

  ctx.save();
  ctx.translate(pos.x, pos.y + bob);
  ctx.scale(facing, 1);
  ctx.lineWidth = 7;
  ctx.lineCap = "round";

  ctx.strokeStyle = "#1b1715";
  ctx.beginPath();
  ctx.moveTo(-11, -58);
  ctx.lineTo(-20, 0);
  ctx.moveTo(11, -58);
  ctx.lineTo(22, 0);
  ctx.stroke();

  ctx.fillStyle = palette.trousers;
  ctx.fillRect(-24, -78, 18, 72);
  ctx.fillRect(6, -78, 18, 72);

  ctx.fillStyle = palette.coat;
  roundRect(-38, -152, 76, 86, 12);
  ctx.fill();
  ctx.fillStyle = palette.shirt;
  ctx.fillRect(-15, -144, 30, 66);

  ctx.strokeStyle = palette.coat;
  ctx.beginPath();
  ctx.moveTo(-34, -136);
  ctx.lineTo(-58, -91 + gesture * -22);
  ctx.moveTo(34, -136);
  ctx.lineTo(58, -95 + gesture * 22);
  ctx.stroke();

  if (id === "militia") {
    ctx.strokeStyle = "#2a1b12";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(45, -150);
    ctx.lineTo(82, -78);
    ctx.stroke();
  }

  ctx.fillStyle = "#c89670";
  ctx.beginPath();
  ctx.arc(0, -182, 24, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = palette.cap;
  ctx.fillRect(-28, -207, 56, 18);
  ctx.fillRect(-12, -219, 38, 16);

  ctx.fillStyle = "#1e1916";
  ctx.beginPath();
  ctx.arc(-8, -183, 2.8, 0, Math.PI * 2);
  ctx.arc(9, -183, 2.8, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#5c3528";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(0, -174, 7, 0.1, Math.PI - 0.1);
  ctx.stroke();

  drawNameplate(palette.name, id);
  ctx.restore();
}

function drawNameplate(name, id) {
  const show = id === "militia"
    ? smoothstep((currentTime - 8) / 4)
    : id === "officer"
      ? smoothstep((currentTime - 15) / 4)
      : smoothstep((currentTime - 27) / 4);
  if (show <= 0) return;
  ctx.save();
  ctx.scale(1 / Math.sign(ctx.getTransform().a || 1), 1);
  ctx.globalAlpha = show * 0.72;
  ctx.fillStyle = "#15120f";
  ctx.fillRect(-72, -268, 144, 30);
  ctx.fillStyle = "#eadcbf";
  ctx.font = "13px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(name, 0, -248);
  ctx.restore();
}

function drawForeground() {
  ctx.fillStyle = "rgba(13, 11, 10, 0.55)";
  ctx.fillRect(-120, 646, 1520, 90);
  ctx.fillStyle = "rgba(0, 0, 0, 0.25)";
  ctx.fillRect(-120, 470, 1520, 10);
}

function drawOverlays(beat) {
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
  ctx.fillRect(0, 0, 1280, 720);

  ctx.fillStyle = "rgba(255, 244, 219, 0.06)";
  for (let i = 0; i < 520; i += 1) {
    const x = (i * 97 + Math.floor(currentTime * 19) * 31) % 1280;
    const y = (i * 53 + Math.floor(currentTime * 23) * 17) % 720;
    if (i % 3 === 0) {
      ctx.fillStyle = "rgba(0, 0, 0, 0.08)";
    } else {
      ctx.fillStyle = "rgba(255, 244, 219, 0.055)";
    }
    ctx.fillRect(x, y, 1.4, 1.4);
  }

  ctx.fillStyle = "rgba(12, 10, 8, 0.78)";
  ctx.fillRect(66, 552, 640, 88);
  ctx.fillStyle = "#d7a84b";
  ctx.font = "700 18px Inter, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(scene.title, 88, 583);
  ctx.fillStyle = "#f4ead7";
  ctx.font = "760 30px Inter, sans-serif";
  ctx.fillText(beat.caption, 88, 620);

  ctx.fillStyle = "rgba(0, 0, 0, 0.62)";
  ctx.fillRect(830, 52, 360, 106);
  ctx.fillStyle = "#d7a84b";
  ctx.font = "700 14px Inter, sans-serif";
  ctx.fillText(beat.label.toUpperCase(), 854, 86);
  ctx.fillStyle = "#cbb899";
  ctx.font = "18px Inter, sans-serif";
  wrapText(beat.copy, 854, 118, 302, 23);
  ctx.restore();
}

function wrapText(text, x, y, maxWidth, lineHeight) {
  const words = text.split(" ");
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      line = word;
      y += lineHeight;
    } else {
      line = test;
    }
  }
  ctx.fillText(line, x, y);
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function renderBeatList() {
  beatList.innerHTML = "";
  for (const beat of scene.beats) {
    const item = document.createElement("button");
    item.className = "beat";
    item.type = "button";
    item.innerHTML = `
      <span class="beat-time">${formatTime(beat.start)}-${formatTime(beat.end)}</span>
      <span class="beat-title">${beat.label}</span>
      <span class="beat-copy">${beat.copy}</span>
    `;
    item.addEventListener("click", () => {
      currentTime = beat.start;
      playing = true;
      syncUi();
    });
    beatList.append(item);
  }
}

function syncUi() {
  const beat = activeBeat();
  scrub.value = String(currentTime);
  timeLabel.textContent = formatTime(currentTime);
  shotLabel.textContent = beat.label;
  playButton.textContent = playing ? "Pause" : "Play";
  for (const [index, element] of [...beatList.children].entries()) {
    element.classList.toggle("is-active", scene.beats[index].id === beat.id);
  }
}

function formatTime(seconds) {
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  return `${String(minutes).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}

function loop(now) {
  const dt = Math.min(0.08, (now - lastFrame) / 1000);
  lastFrame = now;
  if (playing) {
    currentTime += dt;
    if (currentTime >= scene.duration) currentTime = 0;
  }
  drawScene();
  syncUi();
  requestAnimationFrame(loop);
}

playButton.addEventListener("click", () => {
  playing = !playing;
  syncUi();
});

restartButton.addEventListener("click", () => {
  currentTime = 0;
  playing = true;
  syncUi();
});

scrub.addEventListener("input", () => {
  currentTime = Number(scrub.value);
  playing = false;
  syncUi();
});

recordButton.addEventListener("click", () => {
  if (recorder?.state === "recording") {
    recorder.stop();
    recordButton.textContent = "Record";
    return;
  }
  const stream = canvas.captureStream(30);
  recordedChunks = [];
  recorder = new MediaRecorder(stream, { mimeType: "video/webm" });
  recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size > 0) recordedChunks.push(event.data);
  });
  recorder.addEventListener("stop", () => {
    const blob = new Blob(recordedChunks, { type: "video/webm" });
    download.href = URL.createObjectURL(blob);
    download.download = "barcelona-checkpoint-theatre.webm";
    download.hidden = false;
  });
  currentTime = 0;
  playing = true;
  recorder.start();
  recordButton.textContent = "Stop";
});

renderBeatList();
syncUi();
requestAnimationFrame((now) => {
  lastFrame = now;
  loop(now);
});
