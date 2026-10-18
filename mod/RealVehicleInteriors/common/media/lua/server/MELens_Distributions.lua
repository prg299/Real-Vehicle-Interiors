--
-- ME: LENS: RV furniture now and then in the world's loot (sandbox option "RV furniture as
-- loot"), so a camper can be furnished without building everything: the game's own loot lists
-- of camping stores, crates and garages get the pieces at a low chance.
--
require "Items/ProceduralDistributions"

MELens = MELens or {}

local WORLD_LOOT = {
    CampingStoreGear = { MELensRV_Heater = 0.5, MELensRV_Bed = 0.3, MELensRV_Shelf = 0.3 },
    CrateCamping = { MELensRV_Heater = 0.5, MELensRV_Washroom = 0.3, MELensRV_Dinette = 0.3 },
    CrateCarpentry = { MELensRV_Cabinet = 0.8, MELensRV_Wardrobe = 0.5, MELensRV_Shelf = 0.5, MELensRV_Bed = 0.3, MELensRV_Kitchen = 0.3 },
    CrateElectronics = { MELensRV_Fridge = 0.3, MELensRV_Heater = 0.3 },
    GarageMechanics = { MELensRV_Busseat = 0.3 },
}

local function addWorldLoot()
    if MELens.sandbox and not MELens.sandbox("FurnitureInWorld", true) then return end
    local lists = ProceduralDistributions and ProceduralDistributions.list
    if not lists then return end
    for listName, items in pairs(WORLD_LOOT) do
        local list = lists[listName]
        if list and list.items then
            for item, weight in pairs(items) do
                table.insert(list.items, item)
                table.insert(list.items, weight)
            end
        end
    end
end

Events.OnPreDistributionMerge.Add(addWorldLoot)
