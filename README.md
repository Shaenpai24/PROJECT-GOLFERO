
# 🏎️⛳ Project Golfero – AI-Driven Golf Simulation  
### *Where F1-grade engineering meets next-gen AI gameplay.*

<div align="center">

![Golfero Badge](https://img.shields.io/badge/Project_Golfero-AI_Golf_Engine-22c55e?style=for-the-badge&logo=raylib&logoColor=white)
![C/Raylib](https://img.shields.io/badge/C-Raylib_5.0-0ea5e9?style=flat&logo=c&logoColor=white)
![Python](https://img.shields.io/badge/Python-AI%20Brain-8b5cf6?style=flat&logo=python&logoColor=white)
![Linux Only](https://img.shields.io/badge/Linux-Only-eab308?style=flat&logo=linux&logoColor=white)

### **A hybrid Raylib physics engine + Python AI golfer powered by CMA-ES and hierarchical planning.**
</div>

---

<div align="center">
<img src="YOUR_GAMEPLAY_SCREENSHOT.png" width="90%">
</div>

---

## 🚀 What is Project Golfero?

**Project Golfero** is a fully-simulated, high-precision golf engine with:

- A **custom C/Raylib physics engine**
- A **Python AI system** that thinks like a pro golfer
- **Evolutionary optimization (CMA-ES)**
- **Real-time IPC messaging** between C & Python
- **Advanced wind, spin, and terrain modeling**
- **Surrogate physics** for rapid AI evaluations

This is not a toy project — it’s a **research-grade simulation** wrapped in **game-studio execution**.

---

## 🧬 Core System Overview

<div align="center">

```mermaid
flowchart LR
    A[C Engine<br/>Real-time Physics] <-- Pipes --> B[Python AI<br/>Planner + CMA-ES]
    B --> C[Surrogate Physics<br/>100–500 Simulations]
    C --> D[Shot Optimization]
    D --> A
    style A fill:#22c55e,stroke:#15803d,color:#fff
    style B fill:#8b5cf6,stroke:#6d28d9,color:#fff
    style C fill:#0ea5e9,stroke:#0369a1,color:#fff
    style D fill:#f59e0b,stroke:#b45309,color:#fff
````

</div>

---

## ⚡ Feature Highlights

### 🏎️ **F1-Inspired Precision Physics**

* 60 FPS deterministic simulation
* Magnus effect, drag, bounce, terrain friction
* Multi-material course modeling (sand, forest, rough, green…)
* Wind gust system with smoothing + gust prediction

### 🧠 **AI Golfer with Strategic Intelligence**

* High-level planner (Drive / Layup / Chip / Lob / Putt)
* CMA-ES optimizer evaluating 200–500 candidate shots
* Surrogate physics approximating trajectories 1000× faster
* Hazard avoidance + terrain-aware heuristics
* Wind compensation + landing zone selection

### 🔌 **Ultra-Fast IPC Bridge**

* Low-latency named pipes
* Game → AI: Position, wind, terrain, strokes
* AI → Game: Direction, angle, power, spin

### 🎮 **Player Experience**

* Smooth aiming system
* Realistic spin controls
* Visual trajectory indicators
* Clean, responsive Raylib UI

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                          PROJECT GOLFERO                     │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────────────────┐       ┌────────────────────────┐ │
│  │   RAYLIB GAME ENGINE   │◄──────►│     PYTHON AI BRAIN   │ │
│  │  (C, 60 FPS Physics)   │ Pipes  │ (Planner + CMA-ES +   │ │
│  │                        │──────► │  Surrogate Simulator) │ │
│  └────────────────────────┘       └────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 📦 Components

* **main_with_menu.c** → Physics, rendering, UI
* **AI system (Python)** → `/ai_golfer/`

  * `high_level_planner.py`
  * `low_level_optimizer.py`
  * `surrogate_physics.py`
  * `ai_pipe_client.py`

---

## 🎯 Physics Engine

### 🔭 Simulation Constants

```c
#define GRAVITY_ACCEL 800.0f
#define DT 0.016f
#define AIR_DRAG_COEF 1.6f
#define MAGNUS_COEF 0.0012f
#define STOP_SPEED 2.0f
```

### 🧩 Full Pipeline (ASCII)

```
Frame Start
   ↓
Apply Gravity
   ↓
Update Position
   ↓
If Airborne:
    → Apply Drag
    → Apply Wind
    → Apply Magnus Spin
   ↓
If Hit Ground:
    → Bounce
    → Roll + Friction
   ↓
If Speed < Threshold:
    → Stop Ball
```

### 🗺️ Terrain Model

| Terrain | Roll | Bounce | Launch | Notes     |
| ------- | ---- | ------ | ------ | --------- |
| Fairway | 0.96 | 0.60   | 1.00   | Standard  |
| Green   | 0.98 | 0.75   | 1.05   | Fast roll |
| Rough   | 0.80 | 0.55   | 0.85   | Slow      |
| Sand    | 0.45 | 0.05   | 0.35   | Trap      |
| Forest  | 0.40 | 0.00   | 0.40   | Solid     |
| Water   | —    | —      | —      | Hazard    |

---

## 🤖 AI System

### 🧠 High-Level Strategy

```
>150px   → Drive  
80–150px → Layup  
30–80px  → Chip  
<30px    → Putt  
```

### 🧮 CMA-ES Optimization

Optimizes:

* Direction
* Launch angle
* Power
* SpinX
* SpinY

### ⚡ Surrogate Physics

* Lightweight drag + bounce
* Matches full engine patterns
* 100–500 simulations per shot
* Real-time performance

---

## 🔌 IPC Protocol

### Game → AI

```c
struct GameStateMsg {
    float ball_x, ball_y, ball_z;
    float hole_x, hole_y;
    float wind_x, wind_y, wind_strength;
    int strokes;
    bool stopped;
    bool won;
};
```

### AI → Game

```c
struct AICommand {
    float dirx, diry;
    float angle;
    float power;
    float spinx, spiny;
};
```

---

## 🎮 Controls

| Input         | Action             |
| ------------- | ------------------ |
| Mouse Drag    | Aim + Power        |
| Arrow Up/Down | Loft angle         |
| W/S           | Backspin / Topspin |
| A/D           | Left / Right spin  |
| R             | Reset hole         |
| ESC           | Menu               |

---

## 📂 File Structure

```
Project_Golfero/
├── main_with_menu.c
├── golf_menu
├── golf_map.png
├── README.md
└── ai_golfer/
    ├── ai_pipe_client.py
    ├── surrogate_physics.py
    ├── high_level_planner.py
    ├── low_level_optimizer.py
```

---

## 🧪 Build & Run

### 🏗️ Compile (Linux)

```
gcc main_with_menu.c -o golf_menu -lraylib -lm -lpthread -ldl
```

### 🎮 Manual Mode

```
./golf_menu
```

### 🤖 AI Demo

```
# Terminal 1
./golf_menu

# Terminal 2
python3 ai_golfer/ai_pipe_client.py
```

---

## 🛠️ Development Notes

* Tune physics constants in `main_with_menu.c`
* Add terrain via color-coded map regions
* Modify CMA-ES parameters for better convergence
* Adjust planner rules for style variations

---

## 🧯 Troubleshooting

* **AI not connecting?**
  Ensure pipes exist:

  ```
  ls /tmp/golf_*
  ```

* **Ball behaves oddly?**
  Check terrain colors in `golf_map.png`.

* **Slow AI?**
  Switch to fast mode in optimizer.

---

## 🏆 Credits

<div align="center">

### **Built with passion by:**

### **Shashank • Dhanush • Akhil**

</div>

---

<div align="center">

## ⭐ If Project Golfero impressed you, consider starring the repo!

</div>

