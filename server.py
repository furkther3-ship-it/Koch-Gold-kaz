import os
import random
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    init_db, get_user, create_user, update_balance, update_spins, add_xp,
    add_wagered, add_history, get_history, get_referrals_count,
    get_all_users, get_stats, admin_set_balance, admin_add_balance,
    admin_set_spins, admin_set_level, admin_delete_user,
    get_leaderboard,
)

app = FastAPI()

ADMIN_PASSWORD = "Fantan5"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SYMBOLS = ["🍒", "🍋", "🍊", "💎", "7️⃣", "⭐", "🍇", "🔔"]
PAYOUTS = {"🍒": 2, "🍋": 3, "🍊": 4, "💎": 10, "7️⃣": 20, "⭐": 5, "🍇": 7, "🔔": 15}
MINES_GRID = 25

active_mines: dict[int, dict] = {}


class UserRequest(BaseModel):
    user_id: int
    username: str = "player"
    referrer_id: int | None = None


class SlotsRequest(BaseModel):
    user_id: int
    bet: int
    lines: int = 1


class AviatorCashoutRequest(BaseModel):
    user_id: int
    win: int
    bet: int
    multiplier: float


class MinesStartRequest(BaseModel):
    user_id: int
    bet: int
    mines_count: int = 3


class MinesClickRequest(BaseModel):
    user_id: int
    cell_index: int


class WheelSpinRequest(BaseModel):
    user_id: int


class RouletteRequest(BaseModel):
    user_id: int
    bet: int
    choice: str


class CaseOpenRequest(BaseModel):
    user_id: int
    bet: int
    case_id: str = "common"


class AdminBalanceRequest(BaseModel):
    user_id: int
    amount: int


class AdminSpinsRequest(BaseModel):
    user_id: int
    spins: int


class AdminLevelRequest(BaseModel):
    user_id: int
    level: int


def admin_auth(x_admin_token: str = Header(default="")):
    if x_admin_token != ADMIN_PASSWORD:
        raise HTTPException(401, "Invalid admin token")
    return True


CASES_DATA = {
    "common": {
        "name": "Общие",
        "items": [
            {"name": "50 ₽", "value": 50, "mult": 0.5, "rarity": "common"},
            {"name": "100 ₽", "value": 100, "mult": 1.0, "rarity": "common"},
            {"name": "150 ₽", "value": 150, "mult": 1.5, "rarity": "common"},
            {"name": "200 ₽", "value": 200, "mult": 2.0, "rarity": "rare"},
            {"name": "300 ₽", "value": 300, "mult": 3.0, "rarity": "rare"},
            {"name": "500 ₽", "value": 500, "mult": 5.0, "rarity": "legend"},
        ],
    },
    "max": {
        "name": "Макс",
        "items": [
            {"name": "50 ₽", "value": 50, "mult": 0.5, "rarity": "common"},
            {"name": "500 ₽", "value": 500, "mult": 5.0, "rarity": "rare"},
            {"name": "2000 ₽", "value": 2000, "mult": 20.0, "rarity": "legend"},
            {"name": "10000 ₽", "value": 10000, "mult": 100.0, "rarity": "mythic"},
        ],
    },
}


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/register")
async def register(data: UserRequest):
    user = await get_user(data.user_id)
    if user is None:
        user = await create_user(data.user_id, data.username, data.referrer_id)
    return {
        "user_id": user[0], "username": user[1], "balance": user[2],
        "level": user[3], "xp": user[4], "spins": user[5],
        "xp_to_next": user[3] * 100,
        "total_wagered": user[7],
    }


@app.get("/api/user/{user_id}")
async def user_info(user_id: int):
    user = await get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return {
        "user_id": user[0], "username": user[1], "balance": user[2],
        "level": user[3], "xp": user[4], "spins": user[5],
        "xp_to_next": user[3] * 100,
        "total_wagered": user[7],
    }


@app.get("/api/history/{user_id}")
async def history(user_id: int):
    rows = await get_history(user_id, 10)
    return [
        {"game": r[0], "bet": r[1], "win": r[2], "multiplier": r[3], "created_at": r[4]}
        for r in rows
    ]


@app.post("/api/slots/play")
async def slots_play(data: SlotsRequest):
    user = await get_user(data.user_id)
    if user is None:
        raise HTTPException(404, "User not found")

    lines = max(1, min(3, data.lines))
    total_bet = data.bet * lines

    if total_bet <= 0 or total_bet > user[2]:
        raise HTTPException(400, "Недостаточно средств")

    reels = [random.choice(SYMBOLS) for _ in range(3)]
    win = 0
    multiplier = 0.0

    if reels[0] == reels[1] == reels[2]:
        mult = PAYOUTS[reels[0]]
        win = total_bet * mult
        multiplier = float(mult)
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        win = total_bet * 2
        multiplier = 2.0

    new_balance = user[2] - total_bet + win
    await update_balance(data.user_id, new_balance)
    await add_wagered(data.user_id, total_bet)
    await add_history(data.user_id, "Классика", total_bet, win, multiplier)
    lvl = await add_xp(data.user_id, max(5, total_bet // 10))

    return {
        "reels": reels, "bet": total_bet, "win": win,
        "balance": new_balance, "level_info": lvl, "multiplier": multiplier,
    }


@app.post("/api/aviator/cashout")
async def aviator_cashout(data: AviatorCashoutRequest):
    user = await get_user(data.user_id)
    if user is None:
        raise HTTPException(404, "User not found")

    new_balance = user[2] + data.win
    await update_balance(data.user_id, new_balance)
    await add_wagered(data.user_id, data.bet)
    await add_history(data.user_id, "Aviator", data.bet, data.win, data.multiplier)
    lvl = await add_xp(data.user_id, max(5, data.bet // 10))

    return {"balance": new_balance, "level_info": lvl}


@app.post("/api/mines/start")
async def mines_start(data: MinesStartRequest):
    user = await get_user(data.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if data.bet <= 0 or data.bet > user[2]:
        raise HTTPException(400, "Недостаточно средств")

    new_balance = user[2] - data.bet
    await update_balance(data.user_id, new_balance)
    await add_wagered(data.user_id, data.bet)

    mine_positions = set(random.sample(range(MINES_GRID), data.mines_count))
    active_mines[data.user_id] = {
        "bet": data.bet, "mines": mine_positions,
        "opened": set(), "multiplier": 1.0,
        "mines_count": data.mines_count
    }
    return {
        "balance": new_balance,
        "grid_size": MINES_GRID,
        "mines_count": data.mines_count,
    }


@app.post("/api/mines/click")
async def mines_click(data: MinesClickRequest):
    game = active_mines.get(data.user_id)
    if game is None:
        raise HTTPException(400, "Нет активной игры")
    if data.cell_index in game["opened"]:
        raise HTTPException(400, "Клетка уже открыта")

    if data.cell_index in game["mines"]:
        del active_mines[data.user_id]
        user = await get_user(data.user_id)
        lvl = await add_xp(data.user_id, 5)
        return {
            "hit_mine": True, "balance": user[2], "win": 0,
            "mines": list(game["mines"]), "level_info": lvl,
        }

    game["opened"].add(data.cell_index)
    safe_cells = MINES_GRID - game["mines_count"]
    opened_count = len(game["opened"])
    game["multiplier"] = round(1.0 + (opened_count / safe_cells) * 2.0, 2)

    return {
        "hit_mine": False,
        "multiplier": game["multiplier"],
        "opened": list(game["opened"]),
    }


@app.post("/api/mines/cashout")
async def mines_cashout(data: WheelSpinRequest):
    game = active_mines.get(data.user_id)
    if game is None:
        raise HTTPException(400, "Нет активной игры")

    win = int(game["bet"] * game["multiplier"])
    user = await get_user(data.user_id)
    new_balance = user[2] + win
    await update_balance(data.user_id, new_balance)
    await add_history(data.user_id, "Mines", game["bet"], win, game["multiplier"])
    del active_mines[data.user_id]
    lvl = await add_xp(data.user_id, max(5, game["bet"] // 10))

    return {
        "win": win, "balance": new_balance,
        "multiplier": game["multiplier"], "level_info": lvl,
    }


@app.post("/api/wheel/spin")
async def wheel_spin(data: WheelSpinRequest):
    user = await get_user(data.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user[5] <= 0:
        raise HTTPException(400, "Нет доступных спинов")

    prizes = [
        (10, 0.25), (25, 0.20), (50, 0.15), (100, 0.12),
        (200, 0.10), (500, 0.08), (1000, 0.05), (2500, 0.03), (5000, 0.02)
    ]
    total = sum(w for _, w in prizes)
    roll = random.uniform(0, total)
    cum = 0
    win = 10
    for amount, weight in prizes:
        cum += weight
        if roll <= cum:
            win = amount
            break

    new_balance = user[2] + win
    new_spins = user[5] - 1
    await update_balance(data.user_id, new_balance)
    await update_spins(data.user_id, new_spins)

    return {"win": win, "balance": new_balance, "spins": new_spins}


@app.post("/api/roulette/play")
async def roulette_play(data: RouletteRequest):
    user = await get_user(data.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if data.bet <= 0 or data.bet > user[2]:
        raise HTTPException(400, "Недостаточно средств")

    roll = random.randint(0, 36)
    RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    color = "green" if roll == 0 else ("red" if roll in RED else "black")

    win = 0
    mult = 0.0
    c = data.choice

    if c == "green" and roll == 0:
        win = data.bet * 14; mult = 14.0
    elif c == "red" and color == "red":
        win = data.bet * 2; mult = 2.0
    elif c == "black" and color == "black":
        win = data.bet * 2; mult = 2.0
    elif c == "even" and roll != 0 and roll % 2 == 0:
        win = data.bet * 2; mult = 2.0
    elif c == "odd" and roll % 2 == 1:
        win = data.bet * 2; mult = 2.0

    new_balance = user[2] - data.bet + win
    await update_balance(data.user_id, new_balance)
    await add_wagered(data.user_id, data.bet)
    await add_history(data.user_id, "Рулетка", data.bet, win, mult)
    lvl = await add_xp(data.user_id, max(5, data.bet // 10))

    return {
        "roll": roll, "color": color, "win": win,
        "balance": new_balance, "level_info": lvl, "multiplier": mult
    }


@app.get("/api/cases/list")
async def cases_list():
    return {k: {"name": v["name"], "items": v["items"]} for k, v in CASES_DATA.items()}


@app.post("/api/cases/open")
async def case_open(data: CaseOpenRequest):
    user = await get_user(data.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if data.case_id not in CASES_DATA:
        raise HTTPException(400, "Кейс не найден")
    if data.bet < 50 or data.bet > user[2]:
        raise HTTPException(400, "Недостаточно средств")

    items = CASES_DATA[data.case_id]["items"]
    weights = {"common": 50, "rare": 25, "legend": 8, "mythic": 2}
    total_w = sum(weights[i["rarity"]] for i in items)
    roll = random.uniform(0, total_w)
    cum = 0
    won = items[0]
    for it in items:
        cum += weights[it["rarity"]]
        if roll <= cum:
            won = it
            break

    win = int(data.bet * won["mult"])
    new_balance = user[2] - data.bet + win
    await update_balance(data.user_id, new_balance)
    await add_wagered(data.user_id, data.bet)
    await add_history(
        data.user_id,
        f"Кейс {CASES_DATA[data.case_id]['name']}",
        data.bet, win, won["mult"]
    )
    lvl = await add_xp(data.user_id, max(5, data.bet // 10))

    return {
        "item": won, "win": win, "balance": new_balance,
        "level_info": lvl, "bet": data.bet
    }


@app.get("/api/leaderboard")
async def leaderboard():
    data = await get_leaderboard(10)
    return {
        "by_balance": [
            {"user_id": r[0], "username": r[1], "balance": r[2], "level": r[3], "wagered": r[4]}
            for r in data["by_balance"]
        ],
        "by_wins": [
            {"user_id": r[0], "username": r[1], "total_win": r[2]}
            for r in data["by_wins"]
        ],
    }


@app.get("/api/bonuses/{user_id}")
async def bonuses(user_id: int):
    count = await get_referrals_count(user_id)
    user = await get_user(user_id)
    return {"referrals": count, "reward_per_ref": 500, "balance": user[2]}


@app.get("/api/admin/stats", dependencies=[Depends(admin_auth)])
async def admin_stats():
    return await get_stats()


@app.get("/api/admin/users", dependencies=[Depends(admin_auth)])
async def admin_users(limit: int = 200, offset: int = 0):
    rows = await get_all_users(limit, offset)
    return [
        {
            "user_id": r[0], "username": r[1], "balance": r[2],
            "level": r[3], "xp": r[4], "spins": r[5],
            "total_wagered": r[6], "created_at": r[7],
        }
        for r in rows
    ]


@app.post("/api/admin/set-balance", dependencies=[Depends(admin_auth)])
async def admin_set_bal(data: AdminBalanceRequest):
    await admin_set_balance(data.user_id, data.amount)
    return {"ok": True, "balance": data.amount}


@app.post("/api/admin/add-balance", dependencies=[Depends(admin_auth)])
async def admin_add_bal(data: AdminBalanceRequest):
    new_balance = await admin_add_balance(data.user_id, data.amount)
    if new_balance is None:
        raise HTTPException(404, "User not found")
    return {"ok": True, "balance": new_balance}


@app.post("/api/admin/set-spins", dependencies=[Depends(admin_auth)])
async def admin_set_sp(data: AdminSpinsRequest):
    await admin_set_spins(data.user_id, data.spins)
    return {"ok": True, "spins": data.spins}


@app.post("/api/admin/set-level", dependencies=[Depends(admin_auth)])
async def admin_set_lvl(data: AdminLevelRequest):
    await admin_set_level(data.user_id, data.level)
    return {"ok": True, "level": data.level}


@app.post("/api/admin/delete-user", dependencies=[Depends(admin_auth)])
async def admin_del(data: UserRequest):
    await admin_delete_user(data.user_id)
    return {"ok": True}