-- Lasagna food prefab
-- Produced by the crock pot when using 2+ meat + 1+ vegetable/fruit.
-- Garfield gets extra hunger on top of the base stats via his eating hook.

local assets = {
    Asset("ANIM", "anim/lasagna.zip"),
}

local function fn(Sim)
    local inst = CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddAnimState()
    inst.entity:AddSoundEmitter()
    inst.entity:AddNetwork()

    MakeInventoryPhysics(inst)

    inst.AnimState:SetBank("lasagna")
    inst.AnimState:SetBuild("lasagna")
    inst.AnimState:PlayAnimation("idle")

    inst:AddTag("preparedfood")
    inst:AddTag("cooked")

    if not TheWorld.ismastersim then
        return inst
    end

    -- ---- Components ----
    inst:AddComponent("inspectable")
    inst:AddComponent("inventoryitem")
    inst:AddComponent("stackable")
    inst.components.stackable.maxsize = TUNING.STACK_SIZE_SMALLITEM

    inst:AddComponent("edible")
    inst.components.edible.healthvalue  = 20   -- decent healing
    inst.components.edible.hungervalue  = 75   -- very filling
    inst.components.edible.sanityvalue  = 20   -- comfort food
    inst.components.edible.foodtype     = FOODTYPE.MEAT

    inst:AddComponent("perishable")
    inst.components.perishable:SetPerishTime(TUNING.PERISH_MED)
    inst.components.perishable:StartPerishing()
    inst.components.perishable.onperishreplacement = "spoiled_food"

    MakeHauntableLaunch(inst)

    return inst
end

return Prefab("common/inventory/lasagna", fn, assets)
