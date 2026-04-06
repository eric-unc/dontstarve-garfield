-- Garfield character prefab for Don't Starve (base game + RoG)
--
-- DS's MakePlayerCharacter signature:
--   MakePlayerCharacter(name, customprefabs, customassets, customfn, starting_inventory)
-- customfn(inst) is called once — no client/master split like DST.

local MakePlayerCharacter = require("prefabs/player_common")

local assets = {
    Asset("ANIM", "anim/garfield.zip"),
    Asset("ANIM", "anim/ghost_garfield_build.zip"),
}

local start_inv = {
    "morsels",  -- Garfield starts with a piece of meat. Obviously.
}

local MONDAY_BLUES_DURATION = 480  -- ~one game-day in seconds

-- -------------------------------------------------------------------
-- Monday Blues
-- -------------------------------------------------------------------
local function ApplyMondayBlues(inst)
    if inst.components.talker then
        inst.components.talker:Say("I hate Mondays.")
    end
    inst.components.sanity:DoDelta(-10, true)

    inst._monday_blues = true
    inst.components.locomotor.walkspeed = TUNING.WILSON_WALK_SPEED * 0.7
    inst.components.locomotor.runspeed  = TUNING.WILSON_RUN_SPEED  * 0.7

    if inst._monday_task then inst._monday_task:Cancel() end
    inst._monday_task = inst:DoTaskInTime(MONDAY_BLUES_DURATION, function(inst)
        inst._monday_blues = false
        inst.components.locomotor.walkspeed = TUNING.WILSON_WALK_SPEED * 1.1
        inst.components.locomotor.runspeed  = TUNING.WILSON_RUN_SPEED  * 1.1
    end)
end

local function OnNewDay(inst)
    -- GetClock() is the DS API for the world clock (no TheWorld in base DS)
    local clock = GetClock and GetClock()
    local day = clock and clock:GetNumCycles() or 0
    if day % 7 == 0 then
        ApplyMondayBlues(inst)
    end
end

-- -------------------------------------------------------------------
-- Eating bonus
-- -------------------------------------------------------------------
local function OnEatFood(inst, food)
    if food == nil then return end
    if food:HasTag("cooked") and inst.components.hunger then
        inst.components.hunger:DoDelta(20)
    end
    if food.prefab == "lasagna" and inst.components.talker then
        local lines = {
            "Now THAT'S what I call survival.",
            "This makes it all worth it.",
            "I feel like a new cat. A very full new cat.",
        }
        inst.components.talker:Say(lines[math.random(#lines)])
    end
end

-- -------------------------------------------------------------------
-- Single postinit (DS has no client/server split in customfn)
-- -------------------------------------------------------------------
local function postinit(inst)
    -- ---- Appearance ----
    inst.soundsname = "wilson"

    -- Orange fur: DS sprites are white/grey, tinted at render time.
    -- #EF8322 ≈ (0.94, 0.51, 0.13)
    inst.AnimState:SetMultColour(0.94, 0.51, 0.13, 1.0)
    inst.AnimState:SetScale(1.1, 1.1, 1.1)

    -- ---- Tags ----
    inst:AddTag("garfield")
    inst:AddTag("strongstomach")  -- no sanity hit from monster meat

    -- ---- Stats ----
    inst.components.health:SetMaxHealth(150)
    inst.components.hunger:SetMax(250)
    inst.components.sanity:SetMax(150)

    inst.components.hunger.hungerrate = TUNING.WILSON_HUNGER_RATE * 1.25
    inst.components.locomotor.walkspeed = TUNING.WILSON_WALK_SPEED * 1.1
    inst.components.locomotor.runspeed  = TUNING.WILSON_RUN_SPEED  * 1.1

    -- ---- Eating ----
    local old_oneatenfn = inst.components.eater.oneatenfn
    inst.components.eater.oneatenfn = function(eater, food)
        if old_oneatenfn then old_oneatenfn(eater, food) end
        OnEatFood(inst, food)
    end

    -- ---- Monday Blues ----
    inst:ListenForEvent("newday", function() OnNewDay(inst) end)
    inst:DoTaskInTime(0, function() OnNewDay(inst) end)

    -- ---- Starting state ----
    inst.components.health:SetPercent(1)
    inst.components.hunger:SetPercent(0.75)
    inst.components.sanity:SetPercent(0.75)
end

return MakePlayerCharacter("garfield", {}, assets, postinit, start_inv)
