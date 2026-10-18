--
-- ME: LENS camper dashboard: one window for the camper's systems, drawn by ME: LENS itself (no
-- vanilla window chrome, no other mod's code or art): a dark rounded panel with cards for the
-- generator, the battery and lights, the fresh water tank and the appliances; status chips, slim
-- bars, pill buttons and switches. The rounded shapes are white textures drawn by
-- tools-src/art/ui_shapes.py and tinted here. Every control queues a timed action
-- (MELens_Actions.lua), so it works the same as the furniture's own menus.
--
require "ISUI/ISPanel"
require "TimedActions/MELens_Actions"

MELens = MELens or {}
local M = MELens
M.Dashboard = M.Dashboard or {}
local D = M.Dashboard
local U = M.Utilities

------------------------------------------------------------------------------------
-- Style
------------------------------------------------------------------------------------

local TM = getTextManager()
local FONT, FONT_TITLE = UIFont.Small, UIFont.Medium
local FH, FH_TITLE = TM:getFontHeight(FONT), TM:getFontHeight(FONT_TITLE)

local S = {
    pad = 14,               -- around the window's content and between cards
    title = math.max(40, FH_TITLE + 18),
    radius = 10,            -- the window's corners
    cardRadius = 7,
    cardPad = 12,
    row = math.max(26, FH + 10),
    header = math.max(30, FH + 14),
    button = math.max(26, FH + 10),
    barH = 8,
    labelW = 92,
    cardW = 268,
}

-- colours: r, g, b, a
local C = {
    window = { 0.105, 0.108, 0.118, 0.96 },
    titleBar = { 0.075, 0.078, 0.086, 1.0 },
    edge = { 1, 1, 1, 0.07 },
    card = { 0.155, 0.160, 0.172, 1.0 },
    cardEdge = { 1, 1, 1, 0.06 },
    text = { 0.93, 0.93, 0.94, 1.0 },
    muted = { 0.60, 0.62, 0.66, 1.0 },
    track = { 0.075, 0.078, 0.086, 1.0 },
    button = { 0.235, 0.243, 0.262, 1.0 },
    buttonHover = { 0.300, 0.310, 0.334, 1.0 },
    buttonOff = { 0.180, 0.185, 0.198, 1.0 },
    accent = { 0.36, 0.62, 0.96, 1.0 },
    good = { 0.38, 0.80, 0.47, 1.0 },
    warn = { 0.96, 0.70, 0.26, 1.0 },
    bad = { 0.92, 0.38, 0.34, 1.0 },
    idle = { 0.50, 0.52, 0.56, 1.0 },
    fuel = { 0.95, 0.66, 0.22, 1.0 },
    water = { 0.32, 0.62, 0.95, 1.0 },
    warm = { 1.00, 0.58, 0.30, 1.0 },
    cool = { 0.55, 0.82, 1.00, 1.0 },
    close = { 0.86, 0.33, 0.30, 1.0 },
}

local SHAPES = "media/ui/MELens/"
local shapes = {}
local function shape(name)
    if shapes[name] == nil then
        shapes[name] = getTexture(SHAPES .. name .. ".png") or false
    end
    return shapes[name] or nil
end

-- The icon of a vanilla item (by script name), for the cards' headers; nil when the game has none.
local icons = {}
local function itemIcon(fullType)
    if icons[fullType] == nil then
        local ok, tex = pcall(function()
            local script = getScriptManager():FindItem(fullType)
            local icon = script and script:getIcon()
            return icon and getTexture("Item_" .. icon) or nil
        end)
        icons[fullType] = ok and tex or false
    end
    return icons[fullType] or nil
end

------------------------------------------------------------------------------------
-- Drawing helpers (on any ISUIElement)
------------------------------------------------------------------------------------

local function rect(el, x, y, w, h, c, alpha)
    if w > 0 and h > 0 then
        el:drawRect(x, y, w, h, (alpha or 1) * c[4], c[1], c[2], c[3])
    end
end

-- A filled rectangle with rounded corners (the corner shapes tinted), r clamped to fit.
local function roundRect(el, x, y, w, h, r, c, alpha)
    r = math.floor(math.min(r, w / 2, h / 2))
    local a = (alpha or 1) * c[4]
    if r < 1 then
        el:drawRect(x, y, w, h, a, c[1], c[2], c[3])
        return
    end
    el:drawRect(x + r, y, w - 2 * r, h, a, c[1], c[2], c[3])
    el:drawRect(x, y + r, r, h - 2 * r, a, c[1], c[2], c[3])
    el:drawRect(x + w - r, y + r, r, h - 2 * r, a, c[1], c[2], c[3])
    local tl, tr, bl, br = shape("corner_tl"), shape("corner_tr"), shape("corner_bl"), shape("corner_br")
    if tl then
        el:drawTextureScaled(tl, x, y, r, r, a, c[1], c[2], c[3])
        el:drawTextureScaled(tr, x + w - r, y, r, r, a, c[1], c[2], c[3])
        el:drawTextureScaled(bl, x, y + h - r, r, r, a, c[1], c[2], c[3])
        el:drawTextureScaled(br, x + w - r, y + h - r, r, r, a, c[1], c[2], c[3])
    end
end

-- A 1 px outline with the same rounded corners.
local function roundBorder(el, x, y, w, h, r, c, alpha)
    r = math.floor(math.min(r, w / 2, h / 2))
    local a = (alpha or 1) * c[4]
    el:drawRect(x + r, y, w - 2 * r, 1, a, c[1], c[2], c[3])
    el:drawRect(x + r, y + h - 1, w - 2 * r, 1, a, c[1], c[2], c[3])
    el:drawRect(x, y + r, 1, h - 2 * r, a, c[1], c[2], c[3])
    el:drawRect(x + w - 1, y + r, 1, h - 2 * r, a, c[1], c[2], c[3])
    local tl = shape("ring_tl")
    if tl and r >= 1 then
        el:drawTextureScaled(tl, x, y, r, r, a, c[1], c[2], c[3])
        el:drawTextureScaled(shape("ring_tr"), x + w - r, y, r, r, a, c[1], c[2], c[3])
        el:drawTextureScaled(shape("ring_bl"), x, y + h - r, r, r, a, c[1], c[2], c[3])
        el:drawTextureScaled(shape("ring_br"), x + w - r, y + h - r, r, r, a, c[1], c[2], c[3])
    end
end

local function text(el, s, x, y, c, font, alpha)
    el:drawText(s, x, y, c[1], c[2], c[3], (alpha or 1) * c[4], font or FONT)
end

local function textRight(el, s, x, y, c, font)
    el:drawTextRight(s, x, y, c[1], c[2], c[3], c[4], font or FONT)
end

local function textWidth(s, font)
    return TM:MeasureStringX(font or FONT, s)
end

------------------------------------------------------------------------------------
-- Items the controls use
------------------------------------------------------------------------------------

local function petrolItem(player)
    return player:getInventory():getFirstEvalRecurse(function(item)
        return M.Parts.fluidIn(item, "petrol") ~= nil
    end)
end

local function waterItem(player)
    return player:getInventory():getFirstEvalRecurse(function(item)
        return M.Parts.fluidIn(item, "water") ~= nil
    end)
end

-- A propane tank with gas left, if you carry one.
local function propaneTank(player)
    return player:getInventory():getFirstEvalRecurse(function(item)
        return M.Parts.propaneIn(item) > 0
    end)
end

local function scrapItem(player)
    return player:getInventory():getFirstTypeRecurse("ElectronicsScrap")
end

local function say(player, key)
    HaloTextHelper.addBadText(player, getText(key))
end

------------------------------------------------------------------------------------
-- The window
------------------------------------------------------------------------------------

MELensDashboard = ISPanel:derive("MELensDashboard")

function MELensDashboard:new(x, y, player, vehicle)
    local width = S.pad * 3 + S.cardW * 2
    local o = ISPanel.new(self, x, y, width, 300)
    o.player = player
    o.vehicle = vehicle
    o.background = false
    o.moveWithMouse = false
    o.title = getText("IGUI_MELens_DashboardTitle", M.Home.name(vehicle))
    o.cards = {}
    o.controls = {}
    return o
end

function MELensDashboard:initialise()
    ISPanel.initialise(self)
    self:refresh()
end

-- The camper's state, as cards of rows (what render draws) and controls (what a click runs).
-- Rebuilt every refresh, so the window always shows what the camper has now.
function MELensDashboard:refresh()
    local vehicle, player = self.vehicle, self.player
    self.title = getText("IGUI_MELens_DashboardTitle", M.Home.name(vehicle))
    local gen = U.generatorState(vehicle)
    local water = U.waterState(vehicle)
    local oven = U.ovenState(vehicle)
    local power = U.hasPower(vehicle)
    local cards = {}

    -- Generator
    local card = { title = getText("IGUI_MELens_Generator"), icon = itemIcon("Base.Generator"), rows = {}, buttons = {} }
    if gen then
        local status, colour = "IGUI_MELens_Off", C.idle
        if gen.running then
            status, colour = "IGUI_MELens_Running", C.good
        elseif gen.on and gen.fuel <= 0 then
            status, colour = "IGUI_MELens_OutOfFuel", C.bad
        elseif gen.condition <= 0 then
            status, colour = "IGUI_MELens_Broken", C.bad
        end
        card.chip = { text = getText(status), colour = colour }
        table.insert(card.rows, { label = getText("IGUI_MELens_Fuel"), bar = gen.fuel / gen.capacity, colour = C.fuel,
            value = string.format("%.1f / %d L", gen.fuel, gen.capacity) })
        local cond = gen.condition / 100
        table.insert(card.rows, { label = getText("IGUI_MELens_Condition"), bar = cond,
            colour = cond > 0.6 and C.good or (cond > 0.25 and C.warn or C.bad), value = gen.condition .. "%" })
        local petrol, scrap = petrolItem(player), scrapItem(player)
        local fixTip = nil
        if gen.on then fixTip = "IGUI_MELens_TurnOffFirst" elseif not scrap then fixTip = "IGUI_MELens_NeedScrap" end
        card.buttons = {
            { text = getText(gen.on and "ContextMenu_Turn_Off" or "ContextMenu_Turn_On"), primary = true,
              enabled = gen.on or (gen.fuel > 0 and gen.condition > 0),
              tip = (not gen.on and gen.fuel <= 0) and "IGUI_MELens_NoFuel" or nil, fn = self.onGenerator },
            { text = getText("ContextMenu_GeneratorAddFuel"), enabled = gen.fuel < gen.capacity and petrol ~= nil,
              tip = petrol == nil and "IGUI_MELens_NeedPetrol" or nil, fn = self.onAddFuel },
            { text = getText("ContextMenu_GeneratorFix"), enabled = not gen.on and gen.condition < 100 and scrap ~= nil,
              tip = fixTip, fn = self.onFix },
        }
    else
        card.chip = { text = getText("IGUI_MELens_NotInstalled"), colour = C.idle }
    end
    card.column = 1
    table.insert(cards, card)

    -- Battery and lights
    card = { title = getText("IGUI_MELens_Battery"), icon = itemIcon("Base.CarBattery1"), rows = {}, buttons = {} }
    local battery = vehicle:getBattery()
    if battery and battery:getInventoryItem() then
        local charge = M.batteryCharge(vehicle)
        card.chip = (gen and gen.running) and { text = getText("IGUI_MELens_Charging"), colour = C.good } or nil
        table.insert(card.rows, { label = getText("IGUI_MELens_Battery"), bar = charge,
            colour = charge > 0.3 and C.good or (charge > 0.1 and C.warn or C.bad), value = math.floor(charge * 100 + 0.5) .. "%" })
    else
        card.chip = { text = getText("IGUI_MELens_NoBatteryShort"), colour = C.bad }
    end
    local lightsOn = M.lightsSwitchedOn(vehicle)
    table.insert(card.rows, { label = getText("IGUI_MELens_Lights"), switch = lightsOn, fn = self.onLights,
        colour = C.warn, value = getText(lightsOn and "IGUI_MELens_On" or "IGUI_MELens_Off") })
    card.column = 2
    table.insert(cards, card)

    -- Fresh water
    card = { title = getText("IGUI_MELens_Water"), icon = itemIcon("Base.WaterBottle"), rows = {}, buttons = {} }
    if water then
        if water.tainted and water.water > 0 then
            card.chip = { text = getText("IGUI_MELens_Tainted"), colour = C.bad }
        end
        table.insert(card.rows, { label = getText("IGUI_MELens_FreshWater"), bar = water.water / water.capacity, colour = C.water,
            value = string.format("%.1f / %d L", water.water, water.capacity) })
        local item = waterItem(player)
        card.buttons = {
            { text = getText("IGUI_MELens_AddWater"), primary = true, enabled = item ~= nil and water.water < water.capacity,
              tip = item == nil and "IGUI_MELens_NeedWater" or nil, fn = self.onAddWater },
        }
    else
        card.chip = { text = getText("IGUI_MELens_NotInstalled"), colour = C.idle }
    end
    card.column = 1
    table.insert(cards, card)

    -- Propane: what the stove and the heater burn
    local propane = U.propaneOn()
    local gasOut = propane and U.propaneLevel(vehicle) <= 0
    if propane then
        card = { title = getText("IGUI_MELens_Propane"), icon = itemIcon("Base.PropaneTank"), rows = {}, buttons = {} }
        local level, capacity = U.propaneLevel(vehicle), U.PROPANE_CAPACITY
        if gasOut then
            card.chip = { text = getText("IGUI_MELens_PropaneEmpty"), colour = C.bad }
        end
        table.insert(card.rows, { label = getText("IGUI_MELens_PropaneTanks"), bar = level / capacity,
            colour = level > 0.3 and C.fuel or (level > 0.1 and C.warn or C.bad), value = string.format("%.1f / %d", level, capacity) })
        local tank = propaneTank(player)
        local room = level < capacity - 0.001
        card.buttons = {
            { text = getText("ContextMenu_Insert_Propane_Tank"), primary = true, enabled = tank ~= nil and room,
              tip = tank == nil and "IGUI_BBQ_NeedsPropaneTank" or (not room and "IGUI_MELens_PropaneFull" or nil), fn = self.onAddPropane },
        }
        card.column = 1
        table.insert(cards, card)
    end

    -- Appliances
    card = { title = getText("IGUI_MELens_Appliances"), icon = itemIcon("Base.Pot"), rows = {}, buttons = {} }
    local fridge = false
    local profile = M.profileFor(vehicle)
    for index = 1, profile and #profile.spots or 0 do
        if M.Parts.pieceAt(M.Parts.spotPart(vehicle, index)) == "fridge" then fridge = true end
    end
    if not power then
        -- (with propane the stove and the heater do not need power: only a fridge is without it)
        if fridge or not propane then
            card.chip = { text = getText("IGUI_MELens_NoPower"), colour = C.warn }
        end
    elseif not (gen and gen.running) then
        card.chip = { text = getText("IGUI_MELens_ShorePower"), colour = C.good }
    end
    if fridge then
        table.insert(card.rows, { label = getText("IGUI_MELens_Fridge"),
            status = getText(power and "IGUI_MELens_Cooling" or "IGUI_MELens_NoPower"), colour = power and C.cool or C.bad })
    else
        table.insert(card.rows, { label = getText("IGUI_MELens_Fridge"), status = getText("IGUI_MELens_NotInstalled"), colour = C.idle })
    end
    if oven and oven.kitchen and gasOut and not oven.on then
        table.insert(card.rows, { label = getText("IGUI_MELens_StoveLabel"), status = getText("IGUI_MELens_PropaneEmpty"), colour = C.bad })
    elseif oven and oven.kitchen then
        table.insert(card.rows, { label = getText("IGUI_MELens_StoveLabel"), switch = oven.on, fn = self.onStove, colour = C.warm,
            value = getText(oven.on and "IGUI_MELens_On" or "IGUI_MELens_Off") })
    else
        table.insert(card.rows, { label = getText("IGUI_MELens_StoveLabel"), status = getText("IGUI_MELens_NotInstalled"), colour = C.idle })
    end
    if U.heaterPart(vehicle) then
        local heaterOn = U.isOn(vehicle, "heater")
        if gasOut and not heaterOn then
            table.insert(card.rows, { label = getText("IGUI_MELens_Heater"), status = getText("IGUI_MELens_PropaneEmpty"), colour = C.bad })
        else
            table.insert(card.rows, { label = getText("IGUI_MELens_Heater"), switch = heaterOn, fn = self.onHeater, colour = C.warm,
                value = getText(heaterOn and "IGUI_MELens_On" or "IGUI_MELens_Off") })
        end
    else
        table.insert(card.rows, { label = getText("IGUI_MELens_Heater"), status = getText("IGUI_MELens_NotInstalled"), colour = C.idle })
    end
    card.column = 2
    table.insert(cards, card)

    -- Home: its name and the paint on its walls
    card = { title = getText("IGUI_MELens_Home"), icon = itemIcon("Base.Paintbrush"), rows = {}, buttons = {} }
    table.insert(card.rows, { label = getText("IGUI_MELens_Name"), text = M.Home.name(vehicle, profile) })
    local pr, pg, pb = M.Home.paint(vehicle)
    table.insert(card.rows, { label = getText("IGUI_MELens_Walls"), swatch = pr and { pr, pg, pb, 1 } or nil,
        text = pr == nil and getText("IGUI_MELens_OriginalWalls") or nil })
    local brush = M.Home.brushOf and M.Home.brushOf(player) or nil
    local paintable = self:paintChoices()
    card.buttons = {
        { text = getText("IGUI_MELens_Rename"), enabled = true, fn = self.onRename },
        { text = getText("IGUI_MELens_PaintWalls"), enabled = (brush ~= nil and #paintable > 0) or pr ~= nil,
          tip = (pr == nil and (brush == nil or #paintable == 0)) and "IGUI_MELens_NeedPaintAndBrush" or nil, fn = self.onPaint },
    }
    card.column = 2
    table.insert(cards, card)

    self.cards = cards
    self:layout()
end

-- Places the cards in two columns and records where every control is (for clicks and hover).
function MELensDashboard:layout()
    local controls = {}
    local colY = { S.title + S.pad, S.title + S.pad }
    for _, card in ipairs(self.cards) do
        local x = S.pad + (card.column - 1) * (S.cardW + S.pad)
        local y = colY[card.column]
        card.x, card.y, card.w = x, y, S.cardW
        local cy = y + S.header
        for _, row in ipairs(card.rows) do
            row.y = cy
            if row.switch ~= nil then
                row.sw = { x = x + S.cardW - S.cardPad - 36, y = cy + (S.row - 18) / 2, w = 36, h = 18 }
                table.insert(controls, { x = row.sw.x - 4, y = cy, w = row.sw.w + 8, h = S.row, enabled = true, fn = row.fn })
            end
            cy = cy + S.row
        end
        if #card.buttons > 0 then
            cy = cy + 6
            local bx = x + S.cardPad
            for _, b in ipairs(card.buttons) do
                b.w = textWidth(b.text) + 24
                b.x, b.y, b.h = bx, cy, S.button
                bx = bx + b.w + 6
                table.insert(controls, { x = b.x, y = b.y, w = b.w, h = b.h, enabled = b.enabled, fn = b.fn, tip = b.tip, button = b })
            end
            cy = cy + S.button
        end
        card.h = cy - y + S.cardPad
        colY[card.column] = y + card.h + S.pad
    end
    self.controls = controls
    self.closeBox = { x = self.width - S.pad - 24, y = (S.title - 24) / 2, w = 24, h = 24 }
    self:setHeight(math.max(colY[1], colY[2]))
end

local function inside(box, x, y)
    return box and x >= box.x and y >= box.y and x < box.x + box.w and y < box.y + box.h
end

function MELensDashboard:hovered()
    local mx, my = self:getMouseX(), self:getMouseY()
    for _, c in ipairs(self.controls) do
        if inside(c, mx, my) then return c end
    end
    return nil
end

function MELensDashboard:prerender()
    local w, h = self.width, self.height
    -- a soft shadow, the window, its title bar and outline
    roundRect(self, 3, 4, w, h, S.radius + 2, { 0, 0, 0, 0.35 })
    roundRect(self, 0, 0, w, h, S.radius, C.window)
    roundRect(self, 0, 0, w, S.title, S.radius, C.titleBar)
    rect(self, 0, S.title - S.radius, w, S.radius, C.titleBar)
    rect(self, 0, S.title, w, 1, C.edge)
    roundBorder(self, 0, 0, w, h, S.radius, C.edge)
end

function MELensDashboard:render()
    local hover = self:hovered()
    -- title and close
    text(self, self.title, S.pad, (S.title - FH_TITLE) / 2, C.text, FONT_TITLE)
    local cb = self.closeBox
    local overClose = inside(cb, self:getMouseX(), self:getMouseY())
    if overClose then roundRect(self, cb.x, cb.y, cb.w, cb.h, 5, C.close, 0.9) end
    self:drawTextCentre("X", cb.x + cb.w / 2, cb.y + (cb.h - FH) / 2, 1, 1, 1, overClose and 1 or 0.6, FONT)

    for _, card in ipairs(self.cards) do
        roundRect(self, card.x, card.y, card.w, card.h, S.cardRadius, C.card)
        roundBorder(self, card.x, card.y, card.w, card.h, S.cardRadius, C.cardEdge)
        -- header: icon, title, status chip
        local hx = card.x + S.cardPad
        if card.icon then
            self:drawTextureScaledAspect(card.icon, hx, card.y + (S.header - 20) / 2 + 2, 20, 20, 1, 1, 1, 1)
            hx = hx + 26
        end
        text(self, card.title, hx, card.y + (S.header - FH) / 2 + 2, C.text)
        if card.chip then
            local cw = textWidth(card.chip.text) + 18
            local chx, chy = card.x + card.w - S.cardPad - cw, card.y + (S.header - (FH + 4)) / 2 + 2
            roundRect(self, chx, chy, cw, FH + 4, (FH + 4) / 2, card.chip.colour, 0.18)
            self:drawRect(chx + 7, chy + (FH + 4) / 2 - 2, 4, 4, 1, card.chip.colour[1], card.chip.colour[2], card.chip.colour[3])
            text(self, card.chip.text, chx + 14, chy + 2, card.chip.colour)
        end
        rect(self, card.x + S.cardPad, card.y + S.header - 1, card.w - S.cardPad * 2, 1, C.edge)
        -- rows
        for _, row in ipairs(card.rows) do
            local ty = row.y + (S.row - FH) / 2
            text(self, row.label, card.x + S.cardPad, ty, C.muted)
            local vx = card.x + S.cardPad + S.labelW
            local right = card.x + card.w - S.cardPad
            if row.bar then
                local valueW = textWidth(row.value) + 8
                local bw = right - vx - valueW
                local by = row.y + (S.row - S.barH) / 2
                roundRect(self, vx, by, bw, S.barH, S.barH / 2, C.track)
                local fill = math.max(0, math.min(1, row.bar))
                if fill > 0 then roundRect(self, vx, by, math.max(S.barH, bw * fill), S.barH, S.barH / 2, row.colour) end
                textRight(self, row.value, right, ty, C.text)
            elseif row.switch ~= nil then
                text(self, row.value, vx, ty, row.switch and row.colour or C.muted)
                local sw = row.sw
                roundRect(self, sw.x, sw.y, sw.w, sw.h, sw.h / 2, row.switch and row.colour or C.button)
                local knob = shape("knob")
                local kx = row.switch and (sw.x + sw.w - sw.h + 2) or (sw.x + 2)
                if knob then
                    self:drawTextureScaled(knob, kx, sw.y + 2, sw.h - 4, sw.h - 4, 1, 0.97, 0.97, 0.98)
                end
            elseif row.status then
                self:drawRect(vx, row.y + S.row / 2 - 3, 6, 6, 1, row.colour[1], row.colour[2], row.colour[3])
                text(self, row.status, vx + 12, ty, row.colour)
            elseif row.swatch or row.text then
                local tx = vx
                if row.swatch then
                    roundRect(self, vx, row.y + (S.row - 14) / 2, 28, 14, 4, row.swatch)
                    roundBorder(self, vx, row.y + (S.row - 14) / 2, 28, 14, 4, C.edge)
                    tx = vx + 36
                end
                if row.text then text(self, row.text, tx, ty, row.swatch and C.muted or C.text) end
            end
        end
        -- buttons
        for _, b in ipairs(card.buttons) do
            local over = hover and hover.button == b
            local fill = not b.enabled and C.buttonOff or (over and C.buttonHover or C.button)
            if b.enabled and b.primary then fill = over and { 0.45, 0.70, 1.0, 1 } or C.accent end
            roundRect(self, b.x, b.y, b.w, b.h, b.h / 2, fill)
            local tc = b.enabled and C.text or C.muted
            self:drawTextCentre(b.text, b.x + b.w / 2, b.y + (b.h - FH) / 2, tc[1], tc[2], tc[3], b.enabled and 1 or 0.7, FONT)
        end
    end

    -- the control a controller has selected
    local focus = self.joyfocus and self.controls[self.focusIndex or 1]
    if focus then
        roundBorder(self, focus.x - 3, focus.y - 3, focus.w + 6, focus.h + 6, (focus.h + 6) / 2, C.accent)
        if focus.tip and not focus.enabled then hover = focus; hover.atFocus = true end
    end

    -- why a control is off, under the mouse
    if hover and hover.tip then
        local tip = getText(hover.tip)
        local tw, th = textWidth(tip) + 20, FH + 10
        local ax, ay = self:getMouseX() + 12, self:getMouseY() + 18
        if hover.atFocus then ax, ay = hover.x, hover.y + hover.h + 6 end
        local tx = math.max(6, math.min(ax, self.width - tw - 6))
        local ty = math.min(ay, self.height - th - 6)
        roundRect(self, tx, ty, tw, th, 6, { 0.04, 0.04, 0.05, 0.96 })
        roundBorder(self, tx, ty, tw, th, 6, C.edge)
        text(self, tip, tx + 10, ty + 5, C.text)
    end
end

function MELensDashboard:onMouseDown(x, y)
    self.paintPress = nil
    if inside(self.closeBox, x, y) then
        self:close()
        return true
    end
    for _, c in ipairs(self.controls) do
        if inside(c, x, y) then
            if c.enabled and c.fn then
                if c.fn == self.onPaint then
                    self.paintPress = { fn = c.fn, x = c.x, y = c.y, w = c.w, h = c.h }
                else
                    getSoundManager():playUISound("UIActivateButton")
                    c.fn(self)
                end
            elseif c.tip then
                say(self.player, c.tip)
            end
            return true
        end
    end
    -- anywhere else drags the window
    self.dragging = true
    return true
end

function MELensDashboard:onMouseMove(dx, dy)
    if self.dragging then
        self:setX(self:getX() + dx)
        self:setY(self:getY() + dy)
    end
end

function MELensDashboard:onMouseMoveOutside(dx, dy)
    self:onMouseMove(dx, dy)
end

function MELensDashboard:onMouseUp(x, y)
    self.dragging = false
    local press = self.paintPress
    self.paintPress = nil
    -- Opening a left-click menu on mouse-down lets the opening release select
    -- its first option. Finish this button's click before creating that menu.
    if press and inside(press, x, y) then
        for _, c in ipairs(self.controls) do
            if c.enabled and c.fn == press.fn and c.fn == self.onPaint and inside(c, x, y) then
                getSoundManager():playUISound("UIActivateButton")
                c.fn(self)
                break
            end
        end
    end
    return true
end

function MELensDashboard:onMouseUpOutside()
    self.dragging = false
    self.paintPress = nil
end

-- A controller: the d-pad moves between the controls, A uses one, B closes the window.
function MELensDashboard:moveFocus(step)
    local n = #self.controls
    if n == 0 then return end
    self.focusIndex = ((self.focusIndex or 1) - 1 + step) % n + 1
end

function MELensDashboard:onJoypadDirUp() self:moveFocus(-1) end
function MELensDashboard:onJoypadDirLeft() self:moveFocus(-1) end
function MELensDashboard:onJoypadDirDown() self:moveFocus(1) end
function MELensDashboard:onJoypadDirRight() self:moveFocus(1) end

function MELensDashboard:onJoypadDown(button)
    if button == Joypad.AButton then
        local c = self.controls[self.focusIndex or 1]
        if c and c.enabled and c.fn then
            getSoundManager():playUISound("UIActivateButton")
            c.fn(self)
        elseif c and c.tip then
            say(self.player, c.tip)
        end
    elseif button == Joypad.BButton then
        self:close()
    end
end

function MELensDashboard:update()
    ISPanel.update(self)
    if not self.player or self.player:isDead() or not M.Parts.atCamper(self.player, self.vehicle) then
        self:close()
        return
    end
    self:raisePaintMenu()
    self.tick = (self.tick or 0) + 1
    if self.tick % 15 == 0 then
        self:refresh()
    end
end

function MELensDashboard:raisePaintMenu()
    local pending = self.pendingPaintMenu
    if not pending or isMouseButtonDown(0) then return end
    self.pendingPaintMenu = nil
    local context, option = pending.context, pending.option
    -- Native focus queues can raise the Dashboard after its mouse-down handler
    -- opens this menu. Raise only our unchanged paint menu after that click ends.
    if self:isVisible() and context == getPlayerContextMenu(self.player:getPlayerNum())
            and context:isVisible() and option and context.options[1] == option
            and option.target == self and option.onSelect == self.paintWith then
        context:bringToTop()
    end
end

------------------------------------------------------------------------------------
-- Controls
------------------------------------------------------------------------------------

-- From outside, walk to the camper's door first (the generator and the tank fillers are
-- there); inside, the controls are at hand.
function MELensDashboard:queue(action)
    if not self.player:getVehicle() then
        local seat = M.cabinSeat(self.vehicle)
        if seat >= 0 then
            ISTimedActionQueue.add(ISPathFindAction:pathToVehicleSeat(self.player, self.vehicle, seat))
        end
    end
    ISTimedActionQueue.add(action)
end

function MELensDashboard:onGenerator()
    local gen = U.generatorState(self.vehicle)
    if gen then
        self:queue(MELensSwitch:new(self.player, self.vehicle, "generator", not gen.on))
    end
end

function MELensDashboard:onAddFuel()
    local item = petrolItem(self.player)
    if not item then
        say(self.player, "IGUI_MELens_NeedPetrol")
        return
    end
    ISWorldObjectContextMenu.transferIfNeeded(self.player, item)
    self:queue(MELensRefuelGenerator:new(self.player, self.vehicle, item))
end

function MELensDashboard:onFix()
    local item = scrapItem(self.player)
    if not item then
        say(self.player, "IGUI_MELens_NeedScrap")
        return
    end
    ISWorldObjectContextMenu.transferIfNeeded(self.player, item)
    self:queue(MELensRepairGenerator:new(self.player, self.vehicle, item))
end

function MELensDashboard:onLights()
    self:queue(MELensSwitch:new(self.player, self.vehicle, "lights", not M.lightsSwitchedOn(self.vehicle)))
end

function MELensDashboard:onAddWater()
    local item = waterItem(self.player)
    if not item then
        say(self.player, "IGUI_MELens_NeedWater")
        return
    end
    ISWorldObjectContextMenu.transferIfNeeded(self.player, item)
    self:queue(MELensFillWaterTank:new(self.player, self.vehicle, item))
end

function MELensDashboard:onAddPropane()
    local item = propaneTank(self.player)
    if not item then
        say(self.player, "IGUI_BBQ_NeedsPropaneTank")
        return
    end
    ISWorldObjectContextMenu.transferIfNeeded(self.player, item)
    self:queue(MELensInsertPropane:new(self.player, self.vehicle, item))
end

function MELensDashboard:onStove()
    self:queue(MELensSwitch:new(self.player, self.vehicle, "stove", not U.isOn(self.vehicle, "stove")))
end

function MELensDashboard:onHeater()
    self:queue(MELensSwitch:new(self.player, self.vehicle, "heater", not U.isOn(self.vehicle, "heater")))
end

-- Giving the vehicle a name.
function MELensDashboard:onRename()
    local player = self.player
    local width, height = 320, 140
    local box = ISTextBox:new(getCore():getScreenWidth() / 2 - width / 2, getCore():getScreenHeight() / 2 - height / 2,
        width, height, getText("IGUI_MELens_RenameTitle"), M.Home.givenName(self.vehicle) or "", self,
        MELensDashboard.onRenamed, player:getPlayerNum())
    box:initialise()
    box:addToUIManager()
    if JoypadState.players[player:getPlayerNum() + 1] then
        setJoypadFocus(player:getPlayerNum(), box)
    end
end

function MELensDashboard:onRenamed(button)
    if button.internal == "OK" then
        self:queue(MELensRename:new(self.player, self.vehicle, button.parent.entry:getText()))
    end
end

-- The paints in your inventory with enough in the can for a coat: { entry, can }.
function MELensDashboard:paintChoices()
    local list = {}
    local inventory = self.player:getInventory()
    for _, entry in ipairs(M.Home.paints()) do
        local can = inventory:getFirstEvalRecurse(function(item)
            return item:getType() == entry.paint and item:getCurrentUses() >= M.Home.PAINT_USES
        end)
        if can then
            table.insert(list, { entry = entry, can = can })
        end
    end
    return list
end

-- Painting the walls: a menu of the colours you have, and the walls it came with.
function MELensDashboard:onPaint()
    local player = self.player
    local context = ISContextMenu.get(player:getPlayerNum(), getMouseX(), getMouseY())
    local brush = M.Home.brushOf(player)
    if brush then
        for _, choice in ipairs(self:paintChoices()) do
            local option = context:addOption(getText(choice.entry.text), self, MELensDashboard.paintWith,
                choice.can, brush, choice.entry.color)
            option.iconTexture = choice.can:getTex()
        end
    end
    if M.Home.paint(self.vehicle) then
        context:addOption(getText("IGUI_MELens_StripPaint"), self, MELensDashboard.paintWith, nil, nil, nil)
    end
    if JoypadState.players[player:getPlayerNum() + 1] then
        context.origin = self
        context.mouseOver = 1
        setJoypadFocus(player:getPlayerNum(), context)
    end
    self.pendingPaintMenu = { context = context, option = context.options[1] }
end

function MELensDashboard:paintWith(can, brush, color)
    if can then
        ISWorldObjectContextMenu.transferIfNeeded(self.player, can)
        ISWorldObjectContextMenu.transferIfNeeded(self.player, brush)
        self:queue(MELensPaintWalls:new(self.player, self.vehicle, can, brush, color[1], color[2], color[3]))
    else
        self:queue(MELensPaintWalls:new(self.player, self.vehicle, nil, nil, nil, nil, nil))
    end
end

function MELensDashboard:close()
    self.pendingPaintMenu = nil
    self.paintPress = nil
    if self.joyfocus then
        setJoypadFocus(self.player:getPlayerNum(), nil)
    end
    self:setVisible(false)
    self:removeFromUIManager()
    if D.instance == self then
        D.instance = nil
    end
end

function D.open(player, vehicle)
    if D.instance then
        D.instance:close()
    end
    local width = S.pad * 3 + S.cardW * 2
    local window = MELensDashboard:new(getCore():getScreenWidth() / 2 - width / 2, getCore():getScreenHeight() / 2 - 220, player, vehicle)
    window:initialise()
    window:addToUIManager()
    D.instance = window
    local joypad = JoypadState.players[player:getPlayerNum() + 1]
    if joypad then
        setJoypadFocus(player:getPlayerNum(), window)
    end
end
