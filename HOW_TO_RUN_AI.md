Waiting for C game to start...
Opening pipes...
Connected to game!

============================================================
🤖 AI GOLFER - Playing via C visualization
============================================================
Waiting for game state... (50 attempts)
Waiting for game state... (100 attempts)
Waiting for game state... (150 attempts)
Waiting for game state... (200 attempts)
Waiting for game state... (250 attempts)
Waiting for game state... (300 attempts)
Waiting for game state... (350 attempts)
Waiting for game state... (400 attempts)
Waiting for game state... (450 attempts)
Waiting for game state... (500 attempts)
Waiting for game state... (50 attempts)
Waiting for game state... (100 attempts)
Waiting for game state... (150 attempts)
Waiting for game state... (200 attempts)
Waiting for game state... (250 attempts)
Waiting for game state... (300 attempts)
Waiting for game state... (350 attempts)

--- Stroke 1 ---
Ball: (110.0, 490.0)
Hole: (510.0, 90.0)
Distance: 565.7 px
Strategy: DRIVE
  → Sent: dir=(0.707,-0.707) angle=35.0° power=31.2

--- Stroke 2 ---
Ball: (131.5, 469.6)
Hole: (510.0, 90.0)
Distance: 536.1 px
Strategy: DRIVE
  → Sent: dir=(0.706,-0.708) angle=35.0° power=31.2
# How to Run AI Golf

## Simple Steps:

### Terminal 1 - Start the Game
```bash
./golf_menu
```

### Terminal 2 - Start the AI (after clicking AI Demo)
```bash
source ~/bio_env/bin/activate
python3 ai_golfer/ai_pipe_client.py
```

## Order:
1. **Start game** (Terminal 1)
2. **Click "AI Demo"** in the menu
3. **Start Python AI** (Terminal 2)
4. **Watch AI play!**

The game won't freeze anymore - it's ready for the AI to connect anytime!
