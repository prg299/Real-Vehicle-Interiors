-- Developer test driver (test character only): fully kitted military gear for screenshots, and a rifle in
-- the hands. Replaces what the character wears.
local p = getPlayer()
local inv = p:getInventory()
-- already in the kit (a second run would pile the old set on the ground)
for i = 0, p:getWornItems():size() - 1 do
    if p:getWornItems():get(i):getItem():getType() == "Hat_Army" then return "already dressed" end
end
p:clearWornItems()
local log = {}
local function wear(type)
    local ok, item = pcall(function() return inv:AddItem("Base." .. type) end)
    if not (ok and item) then log[#log + 1] = type .. " missing"; return end
    -- (a backpack goes on the back through its own slot, it has no body location)
    local ok2, err = pcall(function()
        if item:canBeEquipped() == "base:back" then p:setClothingItem_Back(item) else p:setWornItem(item:getBodyLocation(), item) end
    end)
    if not ok2 then log[#log + 1] = type .. " " .. tostring(err) end
end
for _, t in ipairs({ "Tshirt_CamoGreen", "Trousers_CamoGreen", "Shoes_ArmyBoots", "Jacket_ArmyCamoGreen", "Vest_BulletArmy",
                     "Hat_Army", "Gloves_LeatherGloves", "Bag_ALICE_BeltSus_Green", "Bag_ALICEpack_Army",
                     "ElbowPad_Left_Military", "ElbowPad_Right_Military", "Kneepad_Left_Military", "Kneepad_Right_Military" }) do
    wear(t)
end
local ok, gun = pcall(function() return inv:AddItem("Base.AssaultRifle") end)
if ok and gun then pcall(function() p:setPrimaryHandItem(gun); p:setSecondaryHandItem(gun) end) else log[#log + 1] = "rifle missing" end
p:resetModel()
triggerEvent("OnClothingUpdated", p)
local names = {}
for i = 0, p:getWornItems():size() - 1 do names[#names + 1] = p:getWornItems():get(i):getItem():getType() end
return "worn: " .. table.concat(names, ",") .. " | " .. table.concat(log, "; ")
