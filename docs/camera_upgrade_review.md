# Camera upgrade review (2026-10-17)

The owner asked what to record with instead of the phone, whether a fisheye
clamped to the net post would help, and later whether anything under €100
works ("in the end we need only 1080 and 30 fps"). This is the answer, with
the measured basis from the calibrations on disk. Prices are what Spanish
shops / comparators showed on 2026-10-17 and move often; check before buying.
Nothing here changes the pipeline; the owed pipeline steps are at the end.

## Verdict

* **Height is the lever, not the camera.** Buy a 3–3.5 m stand that holds in
  sand first.
* **Keep the long-axis geometry** (camera behind a baseline, net facing the
  lens). A fisheye on the net post is a different product geometry.
* **The camera that fits the pipeline** records 1920x1080 at a constant 30 fps
  through a rectilinear lens zoomed to ~55–60° horizontal — the framing the
  phone already has. A wide action-cam view is a regression, not an upgrade.
* **Pick (~€290–330):** DJI Osmo Action 5 Pro; GoPro HERO13 Black if its two
  checks fail. **Under €100:** a used GoPro HERO8 Black (~€100–120) or a spare
  phone; never the €45–80 no-name action cams.

## What the calibrations measure

Camera pose from each video's corners (`court_autocalibration.camera_from_corners`,
pinhole), 1080p frame. Sand detail = ground px per metre of depth at the far
baseline (≈ f·h/D²); far ball = 0.21 m ball at the far baseline (≈ f·0.21/D).

| Setup | Lens height | Behind near baseline | Focal (1080p) | Sand detail, far baseline | Far ball |
|---|---|---|---|---|---|
| Beach 20260920 (phone) | 1.21 m | 7.3 m | 1640 px | 3.7 px/m | 15 px |
| masnou (phone) | 1.55 m | 8.7 m | 1776–1791 px | 4.5 px/m | 15 px |
| vall d'Hebron 20261010 (phone) | 3.3 m | 7.6–8.4 m | 1838–1972 px | 10.8–11.2 px/m | 16–17 px |
| e1–e7 practice clips (phone) | 2.83 m | 8.7 m | 2117 px | 9.8 px/m | 18 px |
| Phone at 3.3 m on the beach, 8 m back (model) | 3.3 m | 8 m | 1640 px | ~9.4 px/m | 14 px |
| Action cam 1080p Linear, no zoom, 92° H (model) | 3.3 m | 8 m | ~927 px | ~5.3 px/m | **~8 px** |
| Action cam 1080p Linear + 2x zoom, ~55° H (model) | 3.3 m | 8 m | ~1854 px | ~10.6 px/m | 16 px |

* Sand detail grows linearly with height (STATUS Learnings: height buys every
  ground read — feet, landings, calibration, receivers' depth). The beach is
  the weak venue because the lens is at 1.2 m, not because of the phone.
* Every validated video has a focal of 1640–2120 px on the 1080p frame
  (≈ 50–60° horizontal, 32–40 mm full-frame equivalent). The phone's lens is
  already right.
* With a fixed near-baseline width in frame, far-court detail is best from
  farther back with a narrower lens (optimum flat between ~8 and 16 m behind
  the baseline). A wide lens closer to the court spends pixels on the sky and
  the near sand: an unzoomed action cam halves the far ball.

## Spec to buy against

1. 1920x1080, 30 fps constant (no "Auto FPS" / auto low light frame-rate
   drop), rectilinear lens mode, ~55–60° horizontal (focal 1650–1850 px at
   1080p; the wider end keeps a near serve toss in frame under a high lens).
2. Records ≥ 2 h untouched in sun at 30 °C+, on its battery or USB-C power. A
   battery swap means lowering the stand = new framing mid-match, and the
   pipeline has no bumped-camera check (open point 36e).
3. Phone app with live preview and start / stop (the camera is 3 m up).
4. Stabilisation and horizon lock off; settings saved in a custom mode so a
   match day needs no settings (owner: "just record").
5. ≥ 16 Mbps at 1080p (the phone's 16 Mbps HEVC works). Light (~150 g) for a
   tall stand; sand / water resistant.
6. File splits that join without missing frames (or no splits).

## Options

| Option | Price (Spain, 2026-10-17) | Verdict |
|---|---|---|
| DJI Osmo Action 5 Pro | ~€285–330 (Amazon.es, PcComponentes; €379 list) | **Pick.** 1/1.3" sensor (matters once cropped to the phone's framing: evening matches), reviewers ran 2–2.5 h at 4K30 with no overheating, 2x video zoom. Verify inside the return window: (a) 1080p30 + Standard (dewarp) + zoom lands at focal 1650–1850 px (a 1-min court clip, read from the calibration); (b) a 30-min recording joins across the 4 GB splits without dropped frames (Action 4 users report a few). |
| GoPro HERO13 Black | ~€330–350 on Amazon.es deals (€449 list; Fnac) | **Fallback if a DJI check fails.** Documented 1080p Linear (92° H, HyperSmooth off) + 2x zoom ≈ 55° H; seamless chapters (~12 GB on a ≥ 64 GB card). Weaker in low light (1/1.9"), long runs need the door open or the Contacto door. |
| Insta360 Ace Pro 2 | ~€330–400 (PcComponentes, MediaMarkt, Fnac) | Same class as the DJI; same two checks. |
| Camcorder (Panasonic HC-VX3, Sony FDR-AX43A) | ~€580–750 / ~€690–800 | Optical zoom frames the court from anywhere and records for hours, but twice the price, not sand-proof, heavier on a stand, EU models often 25/50 fps only. |
| Phone you have + stand | €0 + stand | Turn Auto FPS off or use the Blackmagic Camera app (shutter locked, dropped-frame alert). Heat drops remain, and a phone 3 m up cannot be framed or seen. |

### Under €100 (1080p30 is enough)

| Option | Price | Verdict |
|---|---|---|
| Used GoPro HERO8 Black | ~€100–120 camera only on Wallapop (kits €140–150) | **Pick.** 1080p30 Linear with zoom (≈ 19–39 mm equivalent): zoomed to ~32–35 mm (~1.7x) it is the phone's 55–60° view; Narrow (27 mm, ~67°) is a bit wide. CFR (Auto Low Light only acts at 50/60 fps), live preview in the GoPro app, seamless 4 GB chapters (~10 min each). Weak at dusk (1/2.3"), can overheat in sun (shade it, screen + GPS off), used batteries are often worn (~€20 for new ones, or a power bank with the door off), no warranty from a private seller (protected shipping, ask for a 1080p test clip, check the lens for scratches). |
| Spare or used phone | €0 from a drawer; refurbished iPhone 11 from ~€150 | Same footage domain the ball detector was trained on, right lens at 1x; same heat frame drops as today. |
| New no-name action cams (Wolfang, Apexcam, TIMNUT, Victure) | €45–80 | **No.** Fisheye by default, "4K" claims, unknown frame-rate behaviour, weak apps and batteries. Even the €120–160 Akaso Brave 7 LE (which has a 70° Narrow mode) is rated "noisy, lacks sharpness" by RTINGS, and the far ball is ~15 px. |
| Used camcorder (Sony HDR-CX405, Panasonic HC-V180) | ~€80–150 used (not checked); CX405 new ~€250–360 | Optical zoom = exact framing and hours of recording, but the EU models seen are 25/50 fps, and a 1/5.8" sensor is soft. |

Not recommended at any price: Veo / Pixellot / XbotGo-style cameras (they pan,
zoom or stitch — the pipeline needs a still camera — plus subscriptions), and
360° cameras (stitched, too few pixels per degree).

## Fisheye on the net post: no

* **A new camera geometry.** The calibration is a homography (straight lines;
  a fisheye needs a lens model); the automatic calibration follows a long-axis
  court; team = near / far, the identity read's "which squad is near", the
  attribution signals (AGENTS §5) and every post-run ruler are built and
  measured on the long axis. Rebuilding and re-collecting GT is months, and
  those matches would not be comparable with the published ones (§13).
* **It looks along the net.** Blocker, attacker and setter fall on one image
  line, so the contacts that matter most occlude each other; a player at the
  antenna is 1–2 m from the lens.
* **The post moves when the ball hits the net.** A few px of shake ≈ 1 m on
  the far court (a 4 px far-corner click = 1 m).
* **Servers sit at the frame edges** (≥ 80° off axis), balls hit the post area,
  a rigid arm at head height next to the players is an injury risk, and a
  tournament will not allow it.
* **What it would buy:** which side of the net the ball is on becomes trivial
  (the net plane projects to a line) — worth it only as a second camera later;
  syncing two cameras is its own project.
* The octopus tripod / clamp is useful BEHIND the baseline (fence, lamp post)
  when one stands in the right spot.

## Stand and the rest (~€150–250)

* **Stand:** Neewer 4 m heavy-duty light stand (~€91, Amazon.es; 10 kg load)
  or Manfrotto 1004BAC (3.66 m, ~€145–155, Fotovega / Fotocasión). Use it at
  3–3.5 m and leave the thinnest top section in.
* **In sand:** three empty sandbags filled on site, guy lines with sand pegs.
* **Position:** centred on the long axis, 7–9 m behind the near baseline
  (where every validated video sits). Take the end with the sun behind the
  lens when there is a choice; the pipeline does not care which end.
* **Power:** a USB-C power bank strapped to the stand.
* **Heat:** a white shade over the camera, screen off, GPS off.
* **Card:** 128 GB V30 A2 (SanDisk Extreme 128 GB ~€32). 1080p is ~9–18 GB/h on
  an action cam; the lower bitrate setting keeps files nearer the phone's
  ~7 GB/h for the Drive inbox and the laptop disk.
* **Clock:** set the camera's date and time in its app — match names use the
  local start time (`YYYYMMDD_HHMM_<venue>_<text>`).

## Pipeline steps a new camera owes (not built)

* **No 4K / 2.7K yet.** `ensure_1080` (`src/utils/video_upscale.py`) only
  upscales; a source above 1080p runs at native size with the 1080p px
  constants — silently wrong. `docs/video_recording_guide.md`'s "the system
  auto-scales" is false. A downscale step comes first.
* **No 60 fps.** Frame-count windows and px/frame gates are tuned at ~30 fps
  (decimate to 30 or re-tune).
* **Join chapters losslessly** (ffmpeg concat) before the inbox, keeping the
  timestamps continuous for `frame_times.json`.
* **Ball detector v3** was fine-tuned on phone footage: check raw detections on
  the first new-camera video; a Roboflow top-up if recall drops.
* **Automatic calibration** confirms with a focal length ≥ 3 earlier views
  share: a new camera gives proposals (A = accept) for its first 3 videos.
* **First match with both cameras side by side** (phone + new one): an A/B on
  the same rallies before the switch is relied on.

## Sources

[GoPro HERO13 lens FOV](https://community.gopro.com/s/article/HERO13-Black-Digital-Lenses-FOV-Information?language=en_US) ·
[GoPro HERO13 video settings](https://community.gopro.com/s/article/HERO13-Black-Video-Settings-And-Resolutions?language=en_US) ·
[GoPro HERO13 price (Gizmodo ES)](https://es.gizmodo.com/olvidate-de-las-camaras-de-accion-dji-la-gopro-hero13-black-cae-hasta-rozar-su-precio-minimo-en-la-campana-final-de-liquidacion-de-amazon-2000247825) ·
[GoPro HERO13 at Fnac](https://www.fnac.es/GoPro-HERO13-Black-Videocamara-Videocamara-Sport/a11259768) ·
[GoPro chapters](https://havecamerawilltravel.com/action/gopro-split-video-files/) ·
[GoPro heat](https://havecamerawilltravel.com/action/gopro-getting-hot/) ·
[DJI Osmo Action 5 Pro price, Oct 2026](https://muyinteresante.okdiario.com/bazar/dji-vuelve-a-la-carga-en-octubre-y-hunde-el-precio-de-su-camara-de-accion-osmo-action-5-pro.html) ·
[DJI Osmo Action 5 Pro specs](https://www.dji.com/osmo-action-5-pro/specs) ·
[DJI review, battery / heat (New Atlas)](https://newatlas.com/electronics/dji-osmo-action-5-pro-review/) ·
[DJI split-file frames (forum)](https://forum.dji.com/thread-309519-1-1.html) ·
[Insta360 Ace Pro 2 at PcComponentes](https://www.pccomponentes.com/insta360-ace-pro-2-pack-dual-battery-camara-deportiva-gran-angular-ultrahd-8k) ·
[Insta360 Ace Pro 2 at Fnac](https://www.fnac.es/Pack-Camara-de-accion-Insta360-Ace-Pro-2-2-Baterias-Videocamara-Videocamara-Sport/a11777034) ·
[Panasonic HC-VX3 at Fotocasión](https://www.fotocasion.es/catalogo/videocamara-panasonic-hc-vx3/58137/) ·
[Sony FDR-AX43A at Visanta](https://visanta.com/videocamaras-de-tarjeta/22880-videocamara-sony-4k-fdr-ax43a-4548736141254.html) ·
[Neewer 4 m stand on Amazon.es](https://www.amazon.es/Neewer-Servicio-Acolchado-Fotograf%C3%ADa-Ajustable/dp/B0836Z3HSM) ·
[Manfrotto 1004BAC at Fotovega](https://fotovega.com/iluminacion-accesorios/1606-pie-de-estudio-manfrotto-1004bac-8024221551358.html) ·
[SanDisk Extreme on Amazon.es](https://www.amazon.es/SanDisk-Extreme-Tarjeta-microSDXC-adaptador/dp/B07FCMKK5X) ·
[Samsung Auto FPS](https://thegalaxys24guide.com/how-to-enable-disable-camera-auto-fps-on-samsung-galaxy-s24/) ·
[Blackmagic Camera specs](https://www.blackmagicdesign.com/products/blackmagiccamera/techspecs) ·
[Wallapop GoPro listings](https://es.wallapop.com/electronica/gopro) ·
[Wallapop GoPro Barcelona](https://es.wallapop.com/electronica/gopro/barcelona) ·
[HERO8 video settings (GoPro)](https://community.gopro.com/s/article/HERO8-Black-Video-Resolutions?language=en_US) ·
[HERO8 lens equivalents](https://abekislevitz.com/gopro-hero8-black/) ·
[HERO10 FOV table (Narrow degrees)](https://community.gopro.com/s/article/HERO10-Black-Digital-Lenses-FOV-Informations?language=en_US) ·
[Sub-€100 action cams (Topesdegama)](https://topesdegama.com/listas/gadgets/camaras-deportivas) ·
[Lowi 2026 guide](https://www.lowi.es/blog/mejores-camaras-deportivas-calidad-precio/) ·
[RTINGS Akaso Brave 7 LE](https://www.rtings.com/camera/reviews/akaso/brave-7-le) ·
[Brave 7 LE FOV modes](https://actiongadgetsreviews.com/akaso-brave-7-le-review) ·
[Brave 7 LE price (Globerada)](https://www.globerada.com/precios/akaso-brave-7-le.html) ·
[iPhone 11 refurbished (Back Market)](https://www.backmarket.es/es-es/p/iphone-11) ·
[Sony HDR-CX405 at Fnac](https://www.fnac.es/Videocamara-Sony-HDR-CX405-Videocamara-Videocamara-Memoria-Flash/a1100800) ·
[Sony HDR-CX405 at PcComponentes](https://www.pccomponentes.com/sony-hdr-cx405b-92mp-full-hd)
