-- Vanilla presentation for the shared dashboard state and timed actions.
require "ISUI/ISCollapsableWindow"
require "ISUI/ISButton"

MELensVanillaDashboard = ISCollapsableWindow:derive("MELensVanillaDashboard")
local V = MELensVanillaDashboard
local TM, FONT = getTextManager(), UIFont.Small
local FH = TM:getFontHeight(FONT)
local PAD, GAP, ROW, BUTTON = 10, 16, FH + 9, FH + 8

-- Keep one authority path for both presentations, including revalidation,
-- inventory transfer, paint-menu focus and the normal timed-action queue.
for _, name in ipairs({ "refresh", "update", "raisePaintMenu", "queue", "onGenerator", "onAddFuel",
        "onFix", "onLights", "onAddWater", "onAddPropane", "onStove", "onHeater", "onRename",
        "onRenamed", "paintChoices", "onPaint", "paintWith", "close", "moveFocus",
        "onJoypadDirUp", "onJoypadDirLeft", "onJoypadDirDown", "onJoypadDirRight", "onJoypadDown" }) do
    V[name] = MELensDashboard[name]
end

local function width(text)
    return TM:MeasureStringX(FONT, text or "")
end

function V:new(x, y, player, vehicle)
    local o = ISCollapsableWindow.new(self, x, y, 620, 300)
    o.player, o.vehicle = player, vehicle
    o.title = getText("IGUI_MELens_DashboardTitle", MELens.Home.name(vehicle))
    o.cards, o.controls, o.actionButtons = {}, {}, {}
    o:setResizable(false)
    return o
end

function V:createChildren()
    ISCollapsableWindow.createChildren(self)
    self:refresh()
end

-- ISButtons persist across refreshes so a held press and hover survive live
-- resource/status updates. Recheck the current control again on release.
function V:onControl(button)
    self:refresh()
    for _, control in ipairs(self.controls) do
        if control.fn == button.dashboardAction and control.enabled then
            control.fn(self)
            return
        end
    end
end

function V:placeButton(control, title)
    local button = self.actionButtons[control.fn]
    if not button then
        button = ISButton:new(control.x, control.y, control.w, control.h, title, self, V.onControl)
        button:initialise()
        button.dashboardAction = control.fn
        self.actionButtons[control.fn] = button
        self:addChild(button)
    end
    button:setX(control.x); button:setY(control.y)
    button:setWidth(control.w); button:setHeight(control.h)
    button:setTitle(title)
    button:setEnable(control.enabled)
    button.tooltip = control.tip and getText(control.tip) or nil
    button:setVisible(true)
    control.nativeButton = button
    self.controls[#self.controls + 1] = control
end

function V:layout()
    -- Size columns from translated labels/values; wrap button rows rather than
    -- letting fuel/repair controls extend into the neighboring section.
    local colW = math.max(270, width(getText("ContextMenu_Turn_On")) + width(getText("ContextMenu_Turn_Off")) + 90)
    for _, card in ipairs(self.cards) do
        colW = math.max(colW, width(card.title) + (card.chip and width(card.chip.text) + 18 or 0))
        for _, row in ipairs(card.rows) do
            local value = row.value or row.status or row.text
            colW = math.max(colW, width(row.label) + width(value) + (row.switch ~= nil and 110 or 24))
        end
        for _, b in ipairs(card.buttons) do colW = math.max(colW, width(b.text) + 24) end
    end
    self:setWidth(colW * 2 + PAD * 2 + GAP)
    self.controls = {}
    for _, button in pairs(self.actionButtons) do button:setVisible(false) end
    local colY = { self:titleBarHeight() + PAD, self:titleBarHeight() + PAD }
    for _, card in ipairs(self.cards) do
        local x, y = PAD + (card.column - 1) * (colW + GAP), colY[card.column]
        card.x, card.y, card.w = x, y, colW
        local cy = y + FH + 10
        for _, row in ipairs(card.rows) do
            row.y = cy
            if row.bar ~= nil then
                cy = cy + FH + 7
            elseif row.switch ~= nil then
                local title = getText(row.switch and "ContextMenu_Turn_Off" or "ContextMenu_Turn_On")
                local bw = math.max(80, width(title) + 20)
                self:placeButton({ x = x + colW - bw, y = cy - 2, w = bw, h = BUTTON,
                    enabled = true, fn = row.fn, button = { text = title } }, title)
            end
            cy = cy + ROW
        end
        local bx = x
        if #card.buttons > 0 then
            cy = cy + 4
            for _, b in ipairs(card.buttons) do
                local bw = width(b.text) + 24
                if bx > x and bx + bw > x + colW then bx, cy = x, cy + BUTTON + 5 end
                self:placeButton({ x = bx, y = cy, w = bw, h = BUTTON,
                    enabled = b.enabled, fn = b.fn, tip = b.tip, button = b }, b.text)
                bx = bx + bw + 5
            end
            cy = cy + BUTTON
        end
        card.h = cy - y + PAD
        colY[card.column] = cy + PAD + 8
    end
    self:setHeight(math.max(colY[1], colY[2]))
    -- The standard close button is at the left of the vanilla title bar.
    local b = self.closeButton
    self.closeBox = { x = b:getX(), y = b:getY(), w = b:getWidth(), h = b:getHeight() }
end

function V:render()
    ISCollapsableWindow.render(self)
    if self.isCollapsed then return end
    for _, card in ipairs(self.cards) do
        self:drawText(card.title, card.x, card.y, 1, 1, 1, 1, FONT)
        if card.chip then
            local c = card.chip.colour
            self:drawTextRight(card.chip.text, card.x + card.w, card.y, c[1], c[2], c[3], 1, FONT)
        end
        self:drawRect(card.x, card.y + FH + 3, card.w, 1, 1, .4, .4, .4)
        for _, row in ipairs(card.rows) do
            local x, y, right = card.x, row.y, card.x + card.w
            self:drawText(row.label, x, y, .8, .8, .8, 1, FONT)
            if row.bar ~= nil then
                self:drawTextRight(row.value, right, y, 1, 1, 1, 1, FONT)
                local by, bh = y + FH + 4, 8
                self:drawRect(x, by, card.w, bh, .8, 0, 0, 0)
                local c, fill = row.colour, math.max(0, math.min(1, row.bar))
                self:drawRect(x + 1, by + 1, (card.w - 2) * fill, bh - 2, 1, c[1], c[2], c[3])
                self:drawRectBorder(x, by, card.w, bh, 1, .4, .4, .4)
            elseif row.switch ~= nil then
                local c = row.colour
                local b = self.actionButtons[row.fn]
                self:drawTextRight(row.value, b:getX() - 8, y, c[1], c[2], c[3], 1, FONT)
            elseif row.status then
                local c = row.colour
                self:drawTextRight(row.status, right, y, c[1], c[2], c[3], 1, FONT)
            elseif row.swatch then
                local c = row.swatch
                self:drawRect(right - 36, y + 2, 36, FH - 2, 1, c[1], c[2], c[3])
                self:drawRectBorder(right - 36, y + 2, 36, FH - 2, 1, .4, .4, .4)
            elseif row.text then
                local room = card.w - width(row.label) - 12
                local shown = row.text
                while #shown > 0 and width(shown) > room do shown = string.sub(shown, 1, #shown - 1) end
                self:drawTextRight(shown, right, y, 1, 1, 1, 1, FONT)
            end
        end
    end
    for index, control in ipairs(self.controls) do
        control.nativeButton:setJoypadFocused(self.joyfocus ~= nil and index == (self.focusIndex or 1))
    end
end

function V:onMouseDown(x, y)
    if y < self:titleBarHeight() then ISCollapsableWindow.onMouseDown(self, x, y) end
    return true
end

function V:onMouseUp(x, y)
    ISCollapsableWindow.onMouseUp(self, x, y)
    return true
end
