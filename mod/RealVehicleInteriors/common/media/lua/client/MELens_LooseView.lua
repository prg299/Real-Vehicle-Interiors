--
-- ME: LENS loose items, client side: hands the items lying in the vehicle you are in to the Java part, which
-- draws them as the 3D models the game uses for items on the ground (src/me/lens/rv/Loose.java).
-- Where each lies is in the Floor part (MELens_Loose.lua). Redone twice a second when something changed,
-- and again while a model is still loading. One item that cannot be shown is left out (and said once); a
-- failure of the whole list clears it and is tried again after a few seconds.
--
require "MELens_Cabin"
require "MELens_Loose"

MELens = MELens or {}
local M = MELens
M.LooseView = M.LooseView or {}
local V = M.LooseView
local L = M.Loose
local P = M.Parts

V.LIMIT = 64                 -- the most items drawn in one vehicle (the rest stay in the Floor tab)
V.RETRY_MS = 5000            -- after the whole list failed

local protos = {}            -- item type -> an item to ask the Java part about, or false
local bad = {}               -- item number -> true, for an item that could not be shown
local published = nil        -- what is published now (a signature)
local listed = nil           -- which items lay there when the loot window was last told (a signature)
local publishedVehicle = nil
local timer = 0
local pruneTimer = 0
local retry = false
local lastMs = nil
local failures = 0
local retryAt = 0
local tumbles = {}           -- vehicle id -> how many times things fell by the last look

local function java()
    return M.java()
end

local function num(value)
    return tonumber(value) or 0
end

-- An item of a type, for the Java part to find its model and size by.
function V.proto(fullType)
    local item = protos[fullType]
    if item == nil then
        local ok, made = pcall(instanceItem, fullType)
        item = ok and made or false
        protos[fullType] = item
    end
    return item or nil
end

-- Where an item stands: its recorded height, or the floor if the piece it stood on is gone.
local function heightOf(e, profile, installed)
    if e.s and e.s > 0 and not installed[e.s] then
        return profile.floorY
    end
    return e.y
end

-- Hands one item to the Java part. True when it is in (or cannot be shown), false while its model still loads.
local function addOne(rv, s)
    local e = s.e
    local proto = s.item or V.proto(e.t)
    if not proto or not rv.canShow(proto) then
        return true
    end
    if e.tx then
        return rv.addLooseLook(proto, num(e.x), num(s.y), num(e.z), num(e.r), tostring(e.tx), num(e.tr or 1), num(e.tg or 1), num(e.tb or 1))
    end
    return rv.addLoose(proto, num(e.x), num(s.y), num(e.z), num(e.r))
end

-- The container remains the authority. These display positions never move items
-- into Floor, create loot, or persist a second inventory. Pack the real world
-- models onto empty shelf boards, rotating when needed, without intersecting the
-- cabinet, neighboring items or the next board. Floor placement uses the same
-- measured surfaces and native item-size contract.
V.OPEN_STORAGE = { shelf = true, medlocker = true, equipmentrack = true, workbench = true }
function V.shelfItems(vehicle, profile, budget)
    local groups, pending = {}, false
    local size = M.LooseUI and M.LooseUI.size
    if not size then return {}, true end
    for index, spot in ipairs(profile.spots or {}) do
        local part = P.spotPart(vehicle, index)
        local piece = P.pieceAt(part)
        local container = piece and V.OPEN_STORAGE[piece] and part:getItemContainer()
        if container then
            local boards = {}
            for _, def in ipairs(L.SURFACES[piece]) do
                boards[#boards + 1] = { def = def, used = {} }
            end
            local items, group = {}, {}
            for i = 0, container:getItems():size() - 1 do items[#items + 1] = container:getItems():get(i) end
            table.sort(items, function(a,b) return a:getID() < b:getID() end)
            for _, item in ipairs(items) do
                local w,h,d = size(item)
                if not w then pending = true
                elseif java().canShow(item) then
                    local placed = false
                    for _, board in ipairs(boards) do
                        local b = board.def
                        if not placed and (not b.head or h + .008 <= b.head) then
                            for _, turn in ipairs({0,90}) do
                                local along,deep = w,d
                                if turn == 90 then along,deep = d,w end
                                if not placed and along <= b.a1-b.a0 and deep <= b.d1-b.d0 then
                                    local a = b.a0 + along/2
                                    while a + along/2 <= b.a1 + .0001 and not placed do
                                        local dd = b.d0 + deep/2
                                        while dd + deep/2 <= b.d1 + .0001 and not placed do
                                            local free = true
                                            for _, q in ipairs(board.used) do
                                                if math.abs(a-q.a) < (along+q.w)/2+.008
                                                    and math.abs(dd-q.d) < (deep+q.depth)/2+.008 then free=false;break end
                                            end
                                            if free then
                                                local x,z = P.spotPoint(spot,a,dd)
                                                local look = L.lookOf(item) or {}
                                                local y = profile.floorY+(spot.rise or 0)+b.h
                                                local entry = { id=item:getID(), t=item:getFullType(), x=x,y=y,z=z,
                                                    r=(P.WALLS[spot.wall].rotate+turn)%360, s=index,
                                                    tx=look.tx,tr=look.tr,tg=look.tg,tb=look.tb }
                                                group[#group+1] = { e=entry,y=y,item=item,board=b.name }
                                                board.used[#board.used+1] = {a=a,d=dd,w=along,depth=deep}
                                                placed=true
                                            end
                                            dd=dd+.025
                                        end
                                        a=a+.025
                                    end
                                end
                            end
                        end
                    end
                end
            end
            groups[#groups+1] = group
        end
    end
    -- Share the existing draw budget across racks, so a full first rack cannot
    -- make every later rack appear empty. Loose items keep their existing priority.
    local out, n, more = {}, 1, true
    while #out < budget and more do
        more=false
        for _, group in ipairs(groups) do
            if group[n] and #out < budget then out[#out+1]=group[n];more=true end
        end
        n=n+1
    end
    return out,pending
end

local function publish(vehicle, profile)
    local rv = java()
    local list = L.list(vehicle, profile)
    local installed = {}
    for index = 1, #(profile.spots or {}) do
        installed[index] = P.pieceAt(P.spotPart(vehicle, index)) ~= nil
    end
    local parts, shown = {}, {}
    local limit = M.itemLimit and M.itemLimit() or V.LIMIT
    for _, e in ipairs(list) do
        if #shown >= limit then break end
        if not bad[e.id] then
            local y = heightOf(e, profile, installed)
            parts[#parts + 1] = string.format("%.0f:%.3f:%.3f:%.3f:%.1f:%s", num(e.id), num(e.x), num(y), num(e.z), num(e.r), tostring(e.tx))
            shown[#shown + 1] = { e = e, y = y }
        end
    end
    local shelves, shelfPending = V.shelfItems(vehicle,profile,math.max(0,limit-#shown))
    for _, s in ipairs(shelves) do
        local e=s.e
        parts[#parts+1]=string.format("s%.0f:%s:%.3f:%.3f:%.3f:%.1f",num(e.id),e.t,e.x,e.y,e.z,e.r)
        shown[#shown+1]=s
    end
    local signature = table.concat(parts, ";")
    -- The loot window lists a bag that lies here as a tab of its own; it only learns of one when told.
    -- (Placing, grabbing, dragging into the Floor tab, another player, a server's update: all end here.)
    local ids = {}
    for _, e in ipairs(list) do
        ids[#ids + 1] = e.id
    end
    local present = table.concat(ids, ",")
    if present ~= listed or publishedVehicle ~= vehicle then
        listed = present
        ISInventoryPage.renderDirty = true
    end
    if signature == published and publishedVehicle == vehicle and not retry and not shelfPending then
        return
    end
    if publishedVehicle ~= vehicle then
        rv.retryLoose()                 -- a drawing failure in another vehicle does not carry over
    end
    rv.setLooseBasis(profile.mesh.scale, profile.mesh.lift)
    rv.beginLoose(vehicle)
    local pending = shelfPending
    for _, s in ipairs(shown) do
        local ok, drawn = pcall(addOne, rv, s)
        if not ok then
            bad[s.e.id] = true
            print("[ME_LENS] the item " .. tostring(s.e.t) .. " is not shown: " .. tostring(drawn))
        elseif not drawn then
            pending = true              -- its model is still loading
        end
    end
    rv.endLoose()
    published, publishedVehicle, retry = signature, vehicle, pending
end

-- A crash or hard braking threw what stood on the furniture to the floor (the server counts it in the Floor part):
-- the clatter, and a word.
local function checkTumble(vehicle, player)
    local part = L.floorPart(vehicle)
    local count = part and tonumber(part:getModData().tumbles) or 0
    local id = vehicle:getId()
    local before = tumbles[id]
    tumbles[id] = count
    if before ~= nil and count > before then
        local floor = L.floorContainer(vehicle)
        local item = floor and floor:getItems():size() > 0 and floor:getItems():get(0) or nil
        if item and item:getDropSound() then
            player:playDropItemSound(item)
        else
            player:playSound("DropBag")
        end
        HaloTextHelper.addBadText(player, getText("IGUI_MELens_ItemsFell"))
    end
end

local function onTick()
    local now = getTimestampMs()
    local dt = lastMs and math.min(0.25, math.max(0, (now - lastMs) / 1000)) or 0
    lastMs = now
    local rv = java()
    if not rv then return end
    local player = getSpecificPlayer(0)
    local vehicle = player and not player:isDead() and player:getVehicle()
    local profile = vehicle and M.profileFor(vehicle)
    if profile and M.cabinSeat(vehicle, profile) >= 0 and not M.inVanillaSeat(player, vehicle, profile) then
        timer = timer + dt
        if (timer >= 0.25 or (retry and timer >= 0.1)) and now >= retryAt then
            timer = 0
            local ok, err = pcall(publish, vehicle, profile)
            if ok then
                failures = 0
            else
                -- the whole list: nothing stays up that may be wrong, and it is tried again in a few seconds
                failures = failures + 1
                pcall(rv.clearLoose)
                published, publishedVehicle, retry = nil, nil, false
                retryAt = now + V.RETRY_MS
                if failures <= 3 then
                    print("[ME_LENS] loose items are not shown (trying again): " .. tostring(err))
                end
            end
            local seen, why = pcall(checkTumble, vehicle, player)
            if not seen and failures == 0 then
                print("[ME_LENS] the sound of things falling failed: " .. tostring(why))
            end
        end
        -- single player: forget the places of what was taken out through the loot window
        -- (on a server it is done there, a client may not hold the container's items)
        if not isClient() then
            pruneTimer = pruneTimer + dt
            if pruneTimer >= 1.0 then
                pruneTimer = 0
                L.prune(vehicle)
            end
        end
    elseif publishedVehicle ~= nil or published ~= nil then
        rv.clearLoose()
        published, publishedVehicle, retry, listed = nil, nil, false, nil
    end
end

-- Draws again at once (after an action changed what lies there).
function V.refresh()
    published = nil
end

function V.reset()
    published, publishedVehicle, retry, listed = nil, nil, false, nil
    failures, retryAt = 0, 0
    bad = {}
    protos = {}
    tumbles = {}
    if java() then
        java().resetLoose()
    end
end

-- (Registered once, calling through V, so that a developer's reload of this file takes effect.)
V.onTick = onTick
if not V.hooked then
    V.hooked = true
    Events.OnTick.Add(function() return V.onTick() end)
    Events.OnGameStart.Add(function() V.reset() end)
    Events.OnMainMenuEnter.Add(function() V.reset() end)
end
