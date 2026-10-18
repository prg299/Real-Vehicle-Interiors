-- Production personalization authority contracts with explicit engine doubles.
-- Native text entry, renderer and live multiplayer require separate evidence.
do
    local H = MELens.Home
    local priorServer, priorClient, priorMenu = isServer, isClient, ISPaintMenu
    isServer = function() return true end
    isClient = function() return false end
    ISPaintMenu = { PaintMenuItems = {
        { paint = "PaintGreen", color = { 0.41, 0.80, 0.41 } },
        { paint = "PaintRed", color = { 0.63, 0.10, 0.10 } },
    } }
    local function fixture()
        local v = { data = {}, packets = 0 }
        function v:getModData() return self.data end
        function v:transmitModData() self.packets = self.packets + 1 end
        function v:getX() return 100 end
        function v:getY() return 100 end
        local inv = { owned = {} }
        function inv:contains(item) return self.owned[item] == true end
        local p = { vehicle = v, distance = 0 }
        function p:getVehicle() return self.vehicle end
        function p:getInventory() return inv end
        function p:DistToSquared() return self.distance end
        function p:isTimedActionInstant() return false end
        local function item(kind, uses)
            local i = { kind = kind, uses = uses or 10, consumed = 0 }
            function i:getType() return self.kind end
            function i:getCurrentUses() return self.uses end
            function i:UseAndSync() self.uses = self.uses - 1; self.consumed = self.consumed + 1 end
            inv.owned[i] = true
            return i
        end
        local can, brush = item("PaintGreen"), item("Paintbrush")
        return { v = v, p = p, inv = inv, can = can, brush = brush, item = item }
    end
    local function paint(f, r, g, b)
        return MELensPaintWalls:new(f.p, f.v, f.can, f.brush, r or 0.41, g or 0.80, b or 0.41)
    end
    local f = fixture()
    local rename = MELensRename:new(f.p, f.v, "  My\n Camper  ")
    check(rename:isValid() and rename:complete(), "valid rename completes at the camper")
    check(H.givenName(f.v) == "My Camper" and rename.name == "  My\n Camper  ", "rename sanitizes committed name without altering draft")
    check(f.v.packets == 1, "successful server rename transmits once")
    rename = MELensRename:new(f.p, f.v, "Rejected draft")
    f.p.vehicle, f.p.distance = nil, 100
    check(not rename:complete(), "rename revalidates stale outside reach at completion")
    check(H.givenName(f.v) == "My Camper" and rename.name == "Rejected draft" and f.v.packets == 1, "rejected rename preserves committed name, draft and packets")
    f.p.vehicle = {}
    check(not rename:complete(), "rename cannot reach another vehicle from an occupied vehicle")
    f.p.vehicle, f.p.distance = nil, 1
    check(rename:complete() and H.givenName(f.v) == "Rejected draft", "outside rename remains valid within dashboard reach")
    rename = MELensRename:new(f.p, f.v, "  ABCDEFGHIJKLMNOPQRSTUVWXYZ  ")
    check(rename:complete() and H.givenName(f.v) == "ABCDEFGHIJKLMNOPQRSTUVWX", "rename trims then commits at most 24 characters")
    check(MELensRename:new(f.p, f.v, "   "):complete() and H.givenName(f.v) == nil, "empty trimmed rename restores default name")

    f = fixture()
    local a = paint(f)
    check(a:isValid() and a:complete(), "carried known paint and brush accept shared native palette")
    local r, g, b = H.paint(f.v)
    check(r == 0.41 and g == 0.80 and b == 0.41, "paint commits the selected palette color")
    check(f.can.consumed == 4 and f.can.uses == 6 and f.brush.consumed == 0 and f.v.packets == 1, "one coat consumes exactly four paint uses and preserves brush")
    local strip = MELensPaintWalls:new(f.p, f.v, nil, nil, nil, nil, nil)
    check(strip:complete() and H.paint(f.v) == nil, "strip accepts no supplies and clears committed paint")
    check(f.can.consumed == 4 and f.brush.consumed == 0, "stripping consumes no paint or brush")
    f.brush.kind = "PaintbrushCrafted"
    check(paint(f):complete(), "crafted paintbrush remains supported")

    local function rejected(label, mutate)
        local f = fixture()
        H.setPaint(f.v, 0.63, 0.10, 0.10)
        local a = paint(f)
        check(a:isValid(), label .. " starts valid")
        mutate(f, a)
        local packets, uses, brushUses = f.v.packets, f.can.uses, f.brush.uses
        local ar, ag, ab = a.r, a.g, a.b
        check(not a:complete(), label .. " completion rejected")
        local r, g, b = H.paint(f.v)
        check(r == 0.63 and g == 0.10 and b == 0.10 and f.v.packets == packets,
            label .. " preserves committed paint and sends no update")
        check(f.can.uses == uses and f.brush.uses == brushUses and f.can.consumed == 0
                and (a.r == ar or (a.r ~= a.r and ar ~= ar)) and a.g == ag and a.b == ab,
            label .. " preserves supplies and action draft")
    end
    rejected("exit before completion", function(f) f.p.vehicle = nil end)
    rejected("different vehicle", function(f) f.p.vehicle = {} end)
    rejected("can moved away", function(f) f.inv.owned[f.can] = nil end)
    rejected("brush moved away", function(f) f.inv.owned[f.brush] = nil end)
    rejected("insufficient paint", function(f) f.can.uses = 3 end)
    rejected("wrong drainable item", function(f) f.can.kind = "PetrolCan" end)
    rejected("wrong brush item", function(f) f.brush.kind = "Hammer" end)
    rejected("color does not match can", function(_, a) a.r, a.g, a.b = 0.63, 0.10, 0.10 end)
    rejected("non numeric color", function(_, a) a.g = "0.8" end)
    rejected("partial color", function(_, a) a.b = nil end)
    rejected("out of range color", function(_, a) a.r = 2 end)
    rejected("NaN color", function(_, a) a.r = 0 / 0 end)
    f = fixture()
    strip = MELensPaintWalls:new(f.p, f.v, nil, nil, nil, nil, nil)
    f.p.vehicle = nil
    check(not strip:complete(), "strip revalidates exit without changing paint")
    f.p.vehicle = f.v
    strip.g = 0.5
    check(not strip:complete(), "malformed strip arguments rejected")
    isServer, isClient, ISPaintMenu = priorServer, priorClient, priorMenu
end
