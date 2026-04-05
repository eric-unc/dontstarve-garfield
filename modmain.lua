-- Garfield mod for Don't Starve (base game + Reign of Giants)

PrefabFiles = {
    "garfield",
    "lasagna",
}

Assets = {
    -- Save slot portrait
    Asset("IMAGE", "images/saveslot_portraits/garfield.tex"),
    Asset("ATLAS", "images/saveslot_portraits/garfield.xml"),

    -- Character select screen
    Asset("IMAGE", "images/selectscreen_portraits/garfield.tex"),
    Asset("ATLAS", "images/selectscreen_portraits/garfield.xml"),

    -- Large portrait (in-game sidebar)
    Asset("IMAGE", "images/bigportraits/garfield.tex"),
    Asset("ATLAS", "images/bigportraits/garfield.xml"),

    -- Character name plate on select screen
    Asset("IMAGE", "images/names_garfield.tex"),
    Asset("ATLAS", "images/names_garfield.xml"),
}

-- Register Garfield as a playable character
AddModCharacter("garfield", "MALE")

-- Load speech strings
STRINGS.CHARACTERS.GARFIELD = require("speech_garfield")

-- Load Lasagna food strings
STRINGS.NAMES.LASAGNA = "Lasagna"
STRINGS.RECIPE_DESC.LASAGNA = "A perfect dish. Garfield approves."
STRINGS.CHARACTERS.GENERIC.DESCRIBE.LASAGNA = "That's a beautiful sight."

-- Register Lasagna as a crock pot recipe
-- Requires: 2+ meat + 1+ vegetable/fruit (no filler)
local function LasagnaTest(cooker, ...)
    local items = { ... }
    local meat = 0
    local veggie = 0
    local inedible = 0

    for _, v in ipairs(items) do
        if v.meat ~= nil and v.meat > 0 then
            meat = meat + v.meat
        end
        if (v.vegetable ~= nil and v.vegetable > 0) or (v.fruit ~= nil and v.fruit > 0) then
            veggie = veggie + 1
        end
        if v.inedible ~= nil and v.inedible > 0 then
            inedible = inedible + 1
        end
    end

    return meat >= 2 and veggie >= 1 and inedible == 0
end

AddCookerRecipe("cookpot", {
    name = "lasagna",
    test = LasagnaTest,
    priority = 15, -- higher than most recipes so it doesn't get shadowed
    weight = 1,
    vegetables = 0,
    fruit = 0,
    meat = 2,
    dairy = 0,
    egg = 0,
    inedible = 0,
    mins = { meat = 2 },
})
