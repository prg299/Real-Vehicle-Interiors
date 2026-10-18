-- Disposable media profile only. Queue one real inventory-menu Drop, then lay out
-- the other eleven items as visual fixtures. This is rendering evidence; no mouse
-- or keyboard input is injected. Set MELensGroundPreviewGrid=false for a drop-only take.
require "ISUI/ISInventoryPaneContextMenu"

local p = getPlayer()
if not p or not p:getCurrentSquare() then return "ground preview needs a loaded player" end
if p:getVehicle() then return "exit the vehicle before the ground preview" end
if MELensGroundPreview and MELensGroundPreview.status == "awaiting-normal-drop" then
    return "a furniture drop is already queued"
end

local origin = p:getCurrentSquare()
local cx, cy, cz = origin:getX(), origin:getY(), origin:getZ()
local names = { "Fridge", "Bed", "Dinette", "Kitchen", "Cabinet", "Wardrobe",
    "Washroom", "Heater", "Shelf", "Box", "Busseat", "Busseat2" }
local squares = {}
local grid = MELensGroundPreviewGrid ~= false
for i, name in ipairs(names) do
    if i == 1 or grid then
        local x = cx + ((i - 1) % 4) * 2
        local y = cy + math.floor((i - 1) / 4) * 2
        local sq = getCell():getGridSquare(x, y, cz)
        if not sq or not sq:isFree(false) then
            return "ground preview needs clear loaded ground at " .. x .. "," .. y .. "," .. cz
        end
        squares[i] = sq
    end
end

local item = p:getInventory():AddItem("Base.MELensRV_Fridge")
if not item then return "failed to create the furniture drop item" end
MELensGroundPreview = { status = "awaiting-normal-drop", drop = item, ticks = 0, items = {}, grid = grid }
local review = MELensGroundPreview
ISInventoryPaneContextMenu.dropItem(item, p:getPlayerNum())

local function awaitDrop()
    review.ticks = review.ticks + 1
    local world = item:getWorldItem()
    if world then
        Events.OnTick.Remove(awaitDrop)
        review.status = "normal-drop-complete"
        review.items[1] = { item = item, world = world, type = item:getFullType(),
            model = item:getWorldStaticItem(), x = cx, y = cy, z = cz, normalDrop = true }
        if grid then
            for i = 2, #names do
                local sq = squares[i]
                local placed = sq:AddWorldInventoryItem("Base.MELensRV_" .. names[i], 0.5, 0.5, 0)
                if not placed then
                    review.status = "fixture-failed-" .. names[i]
                    return
                end
                review.items[i] = { item = placed, world = placed:getWorldItem(), type = placed:getFullType(),
                    model = placed:getWorldStaticItem(), x = sq:getX(), y = sq:getY(), z = cz, normalDrop = false }
            end
            review.status = "grid-ready"
        end
        print("[ME_LENS] furniture ground preview " .. review.status .. ", items=" .. #review.items)
    elseif review.ticks > 600 then
        Events.OnTick.Remove(awaitDrop)
        review.status = "normal-drop-timeout"
        print("[ME_LENS] furniture ground preview timed out; item remains available for inspection")
    end
end
Events.OnTick.Add(awaitDrop)
return "queued normal inventory Drop; inspect MELensGroundPreview.status and .items"
