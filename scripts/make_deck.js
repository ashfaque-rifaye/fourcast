// FourCast submission deck — 7 slides, dark UI-matched theme.
// Run: node scripts/make_deck.js   -> assets/FourCast_Deck.pptx
const pptxgen = require("pptxgenjs");

const BG = "0B0E14", CARD = "141A26", LINE = "232C3D", TEXT = "E8EDF7",
      DIM = "8B96AB", ACCENT = "FF5C1A", GOOD = "3DDC84", INK = "0F1420";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5

const F = "Arial";

function base(slide) { slide.background = { color: BG }; }

function card(s, x, y, w, h, opts = {}) {
  s.addShape("roundRect", {
    x, y, w, h, rectRadius: 0.09,
    fill: { color: opts.fill || CARD },
    line: { color: opts.line || LINE, width: opts.lineW || 1 },
  });
}

function chip(s, x, y, w, text, opts = {}) {
  s.addShape("roundRect", {
    x, y, w, h: 0.34, rectRadius: 0.17,
    fill: { color: opts.fill || INK }, line: { color: opts.line || LINE, width: 1 },
  });
  s.addText(text, {
    x, y: y - 0.015, w, h: 0.37, align: "center", fontFace: F,
    fontSize: opts.size || 10.5, color: opts.color || TEXT, margin: 0,
  });
}

function badge(s, x, y, text) {
  s.addShape("roundRect", {
    x, y, w: 1.55, h: 0.32, rectRadius: 0.16,
    fill: { color: BG }, line: { color: GOOD, width: 1 },
  });
  s.addText(text, { x, y: y - 0.015, w: 1.55, h: 0.34, align: "center",
    fontFace: F, fontSize: 10.5, color: GOOD, bold: true, margin: 0 });
}

function footer(s, text) {
  s.addText(text, { x: 0.6, y: 7.02, w: 12.13, h: 0.3, fontFace: F,
    fontSize: 10.5, color: DIM, align: "center", margin: 0 });
}

// ---------- S1 · TITLE ----------
{
  const s = pres.addSlide(); base(s);
  s.addText([
    { text: "Four", options: { color: TEXT } },
    { text: "Cast", options: { color: ACCENT } },
  ], { x: 0.9, y: 1.55, w: 11.5, h: 1.3, fontFace: F, fontSize: 76, bold: true, margin: 0 });
  s.addText("Four voices for every video — grounded captions in four tones, self-judged before you ever see them.",
    { x: 0.95, y: 2.95, w: 10.5, h: 0.65, fontFace: F, fontSize: 19, color: DIM, margin: 0 });

  const styles = [
    ["FORMAL", "objective, factual"],
    ["SARCASTIC", "dry, deadpan"],
    ["HUMOROUS · TECH", "jokes that compile"],
    ["HUMOROUS · NON-TECH", "zero jargon allowed"],
  ];
  styles.forEach((st, i) => {
    const x = 0.95 + i * 2.98;
    card(s, x, 4.15, 2.72, 1.28);
    s.addText(st[0], { x: x + 0.18, y: 4.32, w: 2.4, h: 0.3, fontFace: F,
      fontSize: 12.5, bold: true, color: ACCENT, margin: 0 });
    s.addText(st[1], { x: x + 0.18, y: 4.72, w: 2.4, h: 0.45, fontFace: F,
      fontSize: 12.5, color: TEXT, margin: 0 });
  });

  s.addText("AMD Developer Hackathon: ACT II  ·  Track 2 — Video Captioning  ·  Team mindflayer",
    { x: 0.95, y: 6.15, w: 11.4, h: 0.4, fontFace: F, fontSize: 14, color: TEXT, margin: 0 });
  s.addText("Built in one day on Fireworks AI (AMD-hardware-hosted serverless models)",
    { x: 0.95, y: 6.55, w: 11.4, h: 0.4, fontFace: F, fontSize: 12, color: DIM, margin: 0 });
}

// ---------- S2 · THE TASK ----------
{
  const s = pres.addSlide(); base(s);
  s.addText("The task is a leaderboard, not a demo", { x: 0.6, y: 0.45, w: 12.1, h: 0.7,
    fontFace: F, fontSize: 34, bold: true, color: TEXT, margin: 0 });

  const rows = [
    ["~12 hidden clips", "30s–2min · nature, urban, animals, people, sports, food, weather, tech"],
    ["4 tones per clip", "every requested style must land — a missing style scores zero"],
    ["LLM-judge scoring", "caption accuracy (0–1) + style match (0–1), weighted across everything"],
    ["Container harness", "/input → /output JSON · 10-minute budget · linux/amd64 · public image"],
  ];
  rows.forEach((r, i) => {
    const y = 1.55 + i * 1.18;
    s.addShape("ellipse", { x: 0.75, y: y + 0.08, w: 0.5, h: 0.5, fill: { color: ACCENT } });
    s.addText(String(i + 1), { x: 0.75, y: y + 0.06, w: 0.5, h: 0.52, align: "center",
      fontFace: F, fontSize: 16, bold: true, color: "FFFFFF", margin: 0 });
    s.addText(r[0], { x: 1.5, y, w: 5.0, h: 0.4, fontFace: F, fontSize: 17, bold: true, color: TEXT, margin: 0 });
    s.addText(r[1], { x: 1.5, y: y + 0.4, w: 5.4, h: 0.6, fontFace: F, fontSize: 12.5, color: DIM, margin: 0 });
  });

  card(s, 7.45, 1.65, 5.25, 1.95);
  s.addText("MOST PIPELINES", { x: 7.75, y: 1.9, w: 4.7, h: 0.3, fontFace: F, fontSize: 12,
    bold: true, color: DIM, margin: 0 });
  s.addText("frames  →  one prompt  →  hope", { x: 7.75, y: 2.3, w: 4.7, h: 0.5,
    fontFace: F, fontSize: 19, color: TEXT, margin: 0 });
  s.addText("hallucinated facts · tone drift · one crash zeroes the batch",
    { x: 7.75, y: 2.85, w: 4.7, h: 0.5, fontFace: F, fontSize: 12, color: DIM, margin: 0 });

  card(s, 7.45, 3.9, 5.25, 1.95, { line: ACCENT, lineW: 1.5 });
  s.addText("FOURCAST", { x: 7.75, y: 4.15, w: 4.7, h: 0.3, fontFace: F, fontSize: 12,
    bold: true, color: ACCENT, margin: 0 });
  s.addText("ground → generate → judge → refine", { x: 7.75, y: 4.55, w: 4.7, h: 0.5,
    fontFace: F, fontSize: 19, color: TEXT, margin: 0 });
  s.addText("facts first · executable style contracts · every caption pre-scored on the judge's own axes",
    { x: 7.75, y: 5.1, w: 4.7, h: 0.55, fontFace: F, fontSize: 12, color: DIM, margin: 0 });

  footer(s, "Official participant guide, Track 2 — scoring and harness contract");
}

// ---------- S3 · ARCHITECTURE ----------
{
  const s = pres.addSlide(); base(s);
  s.addText("A caption factory with quality control", { x: 0.6, y: 0.45, w: 12.1, h: 0.7,
    fontFace: F, fontSize: 34, bold: true, color: TEXT, margin: 0 });

  const steps = [
    ["1 · GROUND", "Kimi K2.6 (vision)", "Frames sampled straight off the URL (ffmpeg remote seek). Strict Scene Report: subjects, actions, on-screen text — only what is visible."],
    ["2 · GENERATE", "GLM 5.2", "Three candidates per style against executable style contracts. humorous_non_tech must survive the regex jargon firewall."],
    ["3 · JUDGE", "gpt-oss-120b", "A different model family scores every candidate on accuracy + style — the leaderboard's own two axes — and picks the winner."],
    ["4 · REFINE", "critique loop", "Below 0.85 on either axis, the stylist gets the judge's critique and one rewrite round. Best of pool ships."],
  ];
  steps.forEach((st, i) => {
    const x = 0.6 + i * 3.18;
    card(s, x, 1.6, 2.85, 3.4);
    s.addText(st[0], { x: x + 0.2, y: 1.85, w: 2.45, h: 0.35, fontFace: F, fontSize: 15,
      bold: true, color: ACCENT, margin: 0 });
    chip(s, x + 0.2, 2.3, 2.2, st[1], { size: 10.5 });
    s.addText(st[2], { x: x + 0.2, y: 2.85, w: 2.45, h: 2.0, fontFace: F, fontSize: 11.5,
      color: TEXT, margin: 0 });
    if (i < 3) s.addText("→", { x: x + 2.84, y: 3.05, w: 0.36, h: 0.5, fontFace: F,
      fontSize: 22, bold: true, color: DIM, margin: 0 });
  });

  card(s, 0.6, 5.45, 12.13, 1.15, { fill: INK });
  s.addText([
    { text: "Harness contract:  ", options: { color: DIM, bold: true } },
    { text: "/input/tasks.json  →  container (10-min budget)  →  /output/results.json   ·   linux/amd64   ·   credentials ride inside the image (Track 2 injects none)", options: { color: TEXT } },
  ], { x: 0.95, y: 5.68, w: 11.5, h: 0.7, fontFace: F, fontSize: 13.5, margin: 0 });

  footer(s, "One image, two modes: batch agent (default CMD) or demo UI (uvicorn override)");
}

// ---------- S4 · THE TRICKS ----------
{
  const s = pres.addSlide(); base(s);
  s.addText("Four decisions that move the score", { x: 0.6, y: 0.45, w: 12.1, h: 0.7,
    fontFace: F, fontSize: 34, bold: true, color: TEXT, margin: 0 });

  const cards = [
    ["Scene-report grounding", '"No fact, no joke." The stylist may only use what the vision model verified on screen — hallucination dies before writing starts, and accuracy scores show it.'],
    ["Executable style contracts", "Each tone is a contract with rules (formal: no contractions, no jokes; sarcastic: deadpan overstatement of the mundane) — not a vibe adjective in a prompt."],
    ["The jargon firewall", "One tech word kills a humorous_non_tech candidate before the judge ever sees it (regex + judge double-guard). The trap most teams will fall into, automated away."],
    ["Judge-before-ship", "We cloned the grader. Every shipped caption already beat two siblings on accuracy + style in front of an in-house LLM judge from a different model family."],
  ];
  cards.forEach((c, i) => {
    const x = 0.6 + (i % 2) * 6.37, y = 1.55 + Math.floor(i / 2) * 2.6;
    card(s, x, y, 5.76, 2.3);
    s.addText(c[0], { x: x + 0.3, y: y + 0.25, w: 5.15, h: 0.4, fontFace: F, fontSize: 17.5,
      bold: true, color: ACCENT, margin: 0 });
    s.addText(c[1], { x: x + 0.3, y: y + 0.75, w: 5.15, h: 1.4, fontFace: F, fontSize: 12.5,
      color: TEXT, margin: 0 });
  });

  footer(s, "Model choices are probed, not assumed — scripts/model_matrix.py benchmarks JSON reliability + latency per role");
}

// ---------- S5 · HARNESS ARMOR ----------
{
  const s = pres.addSlide(); base(s);
  s.addText("Engineered to survive the grader", { x: 0.6, y: 0.45, w: 12.1, h: 0.7,
    fontFace: F, fontSize: 34, bold: true, color: TEXT, margin: 0 });

  const stats = [
    ["55s", "3 official example clips, end-to-end"],
    ["≈04:00", "projected for the 12-clip hidden set (10:00 budget)"],
    ["0", "ways one bad clip can zero the batch"],
  ];
  stats.forEach((st, i) => {
    const x = 0.6 + i * 4.19;
    card(s, x, 1.5, 3.85, 1.75);
    s.addText(st[0], { x: x + 0.25, y: 1.68, w: 3.35, h: 0.9, fontFace: F, fontSize: 44,
      bold: true, color: ACCENT, margin: 0 });
    s.addText(st[1], { x: x + 0.25, y: 2.62, w: 3.35, h: 0.5, fontFace: F, fontSize: 12,
      color: DIM, margin: 0 });
  });

  const rows = [
    ["Incremental atomic writes", "results.json is rewritten after every completed clip — a timeout still leaves valid, scoreable output on disk"],
    ["Guaranteed style coverage", "every style always gets a grounded caption; a deterministic fallback beats a missing key (which scores zero)"],
    ["ASCII-safe JSON + strict schema", "the grader's parser can never misread the output; schema self-validated before exit 0"],
    ["Probed fallback chains", "kimi-k2p5 was found dead (500s) and removed; every role has a tested fallback model"],
  ];
  rows.forEach((r, i) => {
    const y = 3.65 + i * 0.78;
    s.addShape("ellipse", { x: 0.75, y: y + 0.06, w: 0.32, h: 0.32, fill: { color: GOOD } });
    s.addText(r[0], { x: 1.3, y, w: 4.4, h: 0.45, fontFace: F, fontSize: 14.5, bold: true, color: TEXT, margin: 0 });
    s.addText(r[1], { x: 5.8, y: y + 0.02, w: 6.9, h: 0.72, fontFace: F, fontSize: 11.5, color: DIM, margin: 0 });
  });

  footer(s, "CI runs the full harness contract offline (SKIP_API mode) on every push before the image reaches GHCR");
}

// ---------- S6 · RECEIPTS ----------
{
  const s = pres.addSlide(); base(s);
  s.addText("Real clips, real scores", { x: 0.6, y: 0.45, w: 12.1, h: 0.7,
    fontFace: F, fontSize: 34, bold: true, color: TEXT, margin: 0 });
  s.addText("Official example clip: garden kitten · scene facts extracted by Kimi K2.6",
    { x: 0.6, y: 1.15, w: 12.1, h: 0.35, fontFace: F, fontSize: 13, color: DIM, margin: 0 });

  const facts = ["a fluffy orange kitten", "walks toward the camera", "tail raised high",
    "dappled sunlight through leaves", "dirt path, scattered debris"];
  let cx = 0.6;
  facts.forEach(fc => {
    const w = 0.42 + fc.length * 0.082;
    chip(s, cx, 1.62, w, fc, { size: 11 });
    cx += w + 0.18;
  });

  card(s, 0.6, 2.4, 12.13, 1.85);
  s.addText("SARCASTIC", { x: 0.95, y: 2.62, w: 3.0, h: 0.3, fontFace: F, fontSize: 12.5,
    bold: true, color: ACCENT, margin: 0 });
  badge(s, 11.0, 2.6, "judge 1.00 / 1.00");
  s.addText('"A fluffy orange kitten emerges from the bushes and walks toward the camera with its tail raised high, because clearly this dirt path with scattered debris is territory worth claiming."',
    { x: 0.95, y: 3.02, w: 11.4, h: 1.05, fontFace: F, fontSize: 15.5, italic: true, color: TEXT, margin: 0 });

  card(s, 0.6, 4.45, 12.13, 1.85);
  s.addText("HUMOROUS · TECH", { x: 0.95, y: 4.67, w: 3.0, h: 0.3, fontFace: F, fontSize: 12.5,
    bold: true, color: ACCENT, margin: 0 });
  badge(s, 11.0, 4.65, "judge 0.95 / 1.00");
  s.addText('"Kitten boots from a stationary state, then begins a slow forward deploy toward the camera, tail raised high as a status indicator."',
    { x: 0.95, y: 5.07, w: 11.4, h: 1.05, fontFace: F, fontSize: 15.5, italic: true, color: TEXT, margin: 0 });

  footer(s, "Scores from FourCast's in-house judge (gpt-oss-120b) — the same accuracy + style axes the leaderboard uses");
}

// ---------- S7 · CLOSE ----------
{
  const s = pres.addSlide(); base(s);
  s.addText("One clip in, every voice out.", { x: 0.9, y: 2.0, w: 11.5, h: 1.0,
    fontFace: F, fontSize: 48, bold: true, color: TEXT, margin: 0 });
  s.addText("The same clip, captioned for LinkedIn, the group chat, tech Twitter, and everyone else — one API call. That is what social teams do by hand, every day, for every post.",
    { x: 0.95, y: 3.15, w: 10.8, h: 0.85, fontFace: F, fontSize: 16, color: DIM, margin: 0 });

  const stack = ["Fireworks AI", "Kimi K2.6", "GLM 5.2", "gpt-oss-120b", "FastAPI", "Docker · linux/amd64"];
  let sx = 0.95;
  stack.forEach(t => {
    const w = 0.5 + t.length * 0.093;
    chip(s, sx, 4.35, w, t, { size: 12 });
    sx += w + 0.22;
  });

  s.addText([
    { text: "github.com/ashfaque-rifaye/fourcast", options: { color: ACCENT, bold: true } },
    { text: "     ·     Team mindflayer     ·     AMD Developer Hackathon: ACT II — Track 2", options: { color: TEXT } },
  ], { x: 0.95, y: 5.35, w: 11.5, h: 0.45, fontFace: F, fontSize: 15, margin: 0 });

  s.addText("FourCast", { x: 0.95, y: 6.45, w: 4.0, h: 0.5, fontFace: F, fontSize: 20, bold: true, color: ACCENT, margin: 0 });
}

pres.writeFile({ fileName: "assets/FourCast_Deck.pptx" })
  .then(() => console.log("deck written: assets/FourCast_Deck.pptx"));
