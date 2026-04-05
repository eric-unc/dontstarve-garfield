-- Garfield character prefab for Don't Starve

local MakePlayerCharacter = require("prefabs/player_common")

local assets = {
    Asset("ANIM", "anim/garfield.zip"),
    Asset("ANIM", "anim/ghost_garfield_build.zip"),
}

local start_inv = {
    -- Garfield starts with a piece of meat because of course he does
    "morsels",
}

-- How often Monday Blues wears off (in seconds; roughly one game-day = 480s)
local MONDAY_BLUES_DURATION = 480

-- -------------------------------------------------------------------
-- Monday Blues
-- Applied at the start of every 7th game-day (day 1, 8, 15, …)
-- Effect: -10 sanity immediately, 20% speed penalty for the day
-- -------------------------------------------------------------------
local function ApplyMondayBlues(inst)
    if inst.components.talker then
        inst.components.talker:Say(STRINGS.CHARACTERS.GARFIELD.MONDAY_ANNOUNCE or "Ugh. Monday.")
    end
    inst.components.sanity:DoDelta(-10, true)

    inst._monday_blues = true
    inst.components.locomotor.walkspeed = TUNING.WILSON_WALK_SPEED * 0.7
    inst.components.locomotor.runspeed  = TUNING.WILSON_RUN_SPEED  * 0.7

    -- Wear off after one full game-day
    if inst._monday_task then inst._monday_task:Cancel() end
    inst._monday_task = inst:DoTaskInTime(MONDAY_BLUES_DURATION, function(inst)
        inst._monday_blues = false
        inst.components.locomotor.walkspeed = TUNING.WILSON_WALK_SPEED * 0.9
        inst.components.locomotor.runspeed  = TUNING.WILSON_RUN_SPEED  * 0.9
    end)
end

local function OnNewDay(inst)
    -- TheWorld.state.cycles counts completed days (0-indexed).
    -- Day 1 = cycles 0, day 8 = cycles 7, etc.  cycles % 7 == 0 catches them all.
    local cycles = TheWorld ~= nil and TheWorld.state ~= nil and TheWorld.state.cycles or 0
    if cycles % 7 == 0 then
        ApplyMondayBlues(inst)
    end
end

-- -------------------------------------------------------------------
-- Eating hooks
-- -------------------------------------------------------------------
local function OnEatFood(inst, food)
    if food == nil then return end

    -- Bonus hunger for cooked foods (Garfield loves a proper meal)
    if food:HasTag("cooked") and inst.components.hunger then
        inst.components.hunger:DoDelta(20)
    end

    -- Special message for lasagna
    if food.prefab == "lasagna" and inst.components.talker then
        local lines = STRINGS.CHARACTERS.GARFIELD.EAT_LASAGNA or {}
        if #lines > 0 then
            inst.components.talker:Say(lines[math.random(#lines)])
        end
    end
end

-- -------------------------------------------------------------------
-- Common post-init (runs on all clients)
-- -------------------------------------------------------------------
local function common_postinit(inst)
    -- Use wilson's sound bank as the fallback while custom audio isn't ready
    inst.soundsname = "wilson"

    -- Tag used by other systems to identify Garfield
    inst:AddTag("garfield")
    -- Cats eat anything without getting sick
    inst:AddTag("strongstomach")
end

-- -------------------------------------------------------------------
-- Master post-init (runs only on the server / singleplayer host)
-- -------------------------------------------------------------------
local function master_postinit(inst)
    -- ---- Stats ----
    inst.components.health:SetMaxHealth(150)
    inst.components.hunger:SetMax(250)
    inst.components.sanity:SetMax(100)

    -- Eats more (he IS a big cat)
    inst.components.hunger.hungerrate = TUNING.WILSON_HUNGER_RATE * 1.25

    -- Lazy cat: slightly slower than Wilson by default
    inst.components.locomotor.walkspeed = TUNING.WILSON_WALK_SPEED * 0.9
    inst.components.locomotor.runspeed  = TUNING.WILSON_RUN_SPEED  * 0.9

    -- ---- Diet ----
    -- Omnivore; strongstomach tag prevents the monster-meat sanity hit
    inst.components.eater:SetDiet(
        { GetTableWithDefault(FOODTYPE, "MEAT", true),
          GetTableWithDefault(FOODTYPE, "VEGGIE", true),
          GetTableWithDefault(FOODTYPE, "GENERIC", true) },
        { GetTableWithDefault(FOODTYPE, "MEAT", true),
          GetTableWithDefault(FOODTYPE, "VEGGIE", true),
          GetTableWithDefault(FOODTYPE, "GENERIC", true) }
    )

    -- Eating callback
    local old_oneatenfn = inst.components.eater.oneatenfn
    inst.components.eater.oneatenfn = function(eater, food)
        if old_oneatenfn then old_oneatenfn(eater, food) end
        OnEatFood(inst, food)
    end

    -- ---- Monday Blues ----
    -- Listen for the global "newday" event (fired every dawn)
    inst:ListenForEvent("newday", OnNewDay, TheWorld)

    -- Check immediately in case the mod is loaded mid-run on day 1/8/15/…
    inst:DoTaskInTime(0, function(inst)
        OnNewDay(inst)
    end)

    -- ---- Start ----
    inst.components.health:SetPercent(1)
    inst.components.hunger:SetPercent(0.75)
    inst.components.sanity:SetPercent(0.75)
end

return MakePlayerCharacter("garfield", {}, assets, common_postinit, master_postinit, start_inv)
