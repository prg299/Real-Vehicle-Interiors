-- Actual production paint-menu scheduling with explicit UI services.
do
    local D, H = MELensDashboard, MELens.Home
    local oldActivated = getActivatedMods
    local enabled = {}
    getActivatedMods = function() return { contains = function(_, id) return enabled[id] == true end } end
    check(not MELens.Dashboard.isNeatActive(), "vanilla is the default without enabled Neat mods")
    for _, id in ipairs({ "NeatUI_Framework", "Neat_Crafting", "Neat_Building", "Neat_Building_UIOnly", "Neat_Rocco", "NeatUI_Equipment" }) do
        enabled = { [id] = true }
        check(MELens.Dashboard.isNeatActive(), "enabled " .. id .. " retains rounded dashboard")
    end
    enabled = { CleanUI = true, SomeNeatMod = true, NeatUI_Framework = false }
    check(not MELens.Dashboard.isNeatActive(), "unrelated names and disabled Neat framework cannot change the default")
    getActivatedMods = oldActivated
    check(MELensVanillaDashboard.refresh == D.refresh and MELensVanillaDashboard.queue == D.queue
        and MELensVanillaDashboard.onPaint == D.onPaint, "both dashboard views share state, timed actions and paint behavior")
    local calls, allow = 0, true
    local fn = function() calls = calls + 1 end
    local vanilla = setmetatable({}, { __index = MELensVanillaDashboard })
    function vanilla:refresh() self.controls = {{ fn = fn, enabled = allow }} end
    vanilla:onControl({ dashboardAction = fn })
    check(calls == 1, "vanilla release activates the current enabled action once")
    allow = false
    vanilla:onControl({ dashboardAction = fn })
    check(calls == 1, "vanilla release revalidates an action disabled while held")
    allow = true
    vanilla:onControl({ dashboardAction = function() end })
    check(calls == 1, "removed vanilla controls cannot activate a stale action")
    local mouseDown, current = false, nil
    isMouseButtonDown = function(button) check(button == 0, "paint raise checks only opening left button"); return mouseDown end
    getPlayerContextMenu = function(player) check(player == 0, "paint raise uses its own player"); return current end
    local function fixture()
        local p = { getPlayerNum = function() return 0 end }
        local w = setmetatable({ player = p, visible = true }, { __index = D })
        function w:isVisible() return self.visible end
        local menu = { visible = true, raises = 0, options = {} }
        function menu:isVisible() return self.visible end
        function menu:bringToTop() self.raises = self.raises + 1 end
        local option = { target = w, onSelect = w.paintWith }
        menu.options[1] = option
        w.pendingPaintMenu = { context = menu, option = option }
        current = menu
        return w, menu, option
    end
    local w, menu = fixture()
    mouseDown = true
    w:raisePaintMenu()
    check(menu.raises == 0 and w.pendingPaintMenu ~= nil, "opening press cannot raise menu or auto-select first paint")
    mouseDown = false
    w:raisePaintMenu()
    check(menu.raises == 1 and w.pendingPaintMenu == nil, "released opening click raises owned paint menu once")
    w:raisePaintMenu()
    check(menu.raises == 1, "paint menu is not repeatedly raised during later updates")
    local function rejected(label, change)
        local w, menu, option = fixture()
        change(w, menu, option)
        w:raisePaintMenu()
        check(menu.raises == 0 and w.pendingPaintMenu == nil, label .. " cannot steal UI focus")
    end
    rejected("closed menu", function(_, menu) menu.visible = false end)
    rejected("hidden Dashboard", function(w) w.visible = false end)
    rejected("different current menu", function() current = {} end)
    rejected("reused context options", function(_, menu) menu.options[1] = {} end)
    rejected("retargeted pooled option", function(_, _, option) option.target = {} end)
    rejected("different menu action", function(_, _, option) option.onSelect = function() end end)
    rejected("empty menu", function(w, menu) menu.options[1] = nil; w.pendingPaintMenu.option = nil end)

    local sounds = 0
    getSoundManager = function() return { playUISound = function(_, name)
        check(name == "UIActivateButton", "paint release uses normal activation sound")
        sounds = sounds + 1
    end } end
    local function pressFixture()
        local w = fixture()
        w.pendingPaintMenu, w.paintCalls, w.controls = nil, 0, {}
        function w:onPaint() self.paintCalls = self.paintCalls + 1 end
        w.controls[1] = { x = 5, y = 5, w = 20, h = 20, enabled = true, fn = w.onPaint }
        return w, w.controls[1]
    end
    w = pressFixture()
    check(w:onMouseDown(10, 10) == true and w.paintCalls == 0 and sounds == 0 and w.paintPress ~= nil,
        "paint button consumes press without opening a left-click menu")
    -- Refresh rebuilds the control table during a held press. Revalidate its
    -- semantic action and bounds, rather than requiring old table identity.
    w.controls[1] = { x = 5, y = 5, w = 20, h = 20, enabled = true, fn = w.onPaint }
    check(w:onMouseUp(10, 10) == true and w.paintCalls == 1 and sounds == 1 and w.paintPress == nil,
        "same enabled paint control activates once on its completed release")
    w:onMouseUp(10, 10)
    check(w.paintCalls == 1 and sounds == 1, "orphan mouse-up cannot reopen paint menu")
    local function rejectedPress(label, change, outside)
        local w, control = pressFixture()
        w:onMouseDown(10, 10)
        change(w, control)
        if outside then w:onMouseUpOutside() else w:onMouseUp(10, 10) end
        check(w.paintCalls == 0 and w.paintPress == nil, label .. " cancels the pending paint click")
    end
    rejectedPress("release outside window", function() end, true)
    rejectedPress("control disabled while held", function(_, c) c.enabled = false end)
    rejectedPress("control moved while held", function(_, c) c.x = 50 end)
    rejectedPress("control removed while held", function(w) w.controls = {} end)
    rejectedPress("paint callback changed while held", function(w) function w:onPaint() self.paintCalls = 99 end end)
    w = pressFixture()
    w:onMouseDown(10, 10); w:onMouseUp(30, 30)
    check(w.paintCalls == 0 and w.paintPress == nil, "release elsewhere inside Dashboard cancels paint click")
    w = pressFixture()
    w.controls[1].enabled = false
    w:onMouseDown(10, 10); w:onMouseUp(10, 10)
    check(w.paintCalls == 0 and w.paintPress == nil, "disabled paint control cannot arm on press")
    w = pressFixture()
    local otherCalls = 0
    w.controls[2] = { x = 40, y = 5, w = 20, h = 20, enabled = true, fn = function() otherCalls = otherCalls + 1 end }
    w:onMouseDown(10, 10); w:onMouseDown(45, 10); w:onMouseUp(10, 10)
    check(otherCalls == 1 and w.paintCalls == 0 and w.paintPress == nil,
        "new press cancels stale paint while preserving other controls' mouse-down behavior")

    w, menu = fixture()
    w.vehicle = { getModData = function() return {} end }
    local oldBrush = H.brushOf
    H.brushOf = function() return {} end
    function w:paintChoices() return {{ can = { getTex = function() return nil end },
        entry = { text = "Green", color = { .41, .8, .41 } } }} end
    ISContextMenu = { get = function(player) check(player == 0, "paint menu belongs to its invoking player"); menu.options = {}; return menu end }
    function menu:addOption(name, target, fn)
        local option = { name = name, target = target, onSelect = fn }
        self.options[#self.options + 1] = option
        return option
    end
    JoypadState = { players = {} }
    getMouseX, getMouseY = function() return 10 end, function() return 20 end
    w:onPaint()
    check(w.pendingPaintMenu.context == menu and w.pendingPaintMenu.option == menu.options[1], "onPaint records its exact created menu and option")
    check(menu.raises == 0 and menu.options[1].target == w and menu.options[1].onSelect == w.paintWith,
        "onPaint defers only its own genuine paint action")
    H.brushOf = oldBrush
    function w:setVisible(value) self.visible = value end
    function w:removeFromUIManager() self.removed = true end
    w.paintPress = { fn = w.onPaint }
    w:close()
    check(w.pendingPaintMenu == nil and w.paintPress == nil and w.removed and not w.visible, "Dashboard close clears deferred menu focus and paint press")
    for _, name in ipairs({ "ISPanel", "ISCollapsableWindow", "UIFont", "getTextManager", "isMouseButtonDown",
            "getPlayerContextMenu", "ISContextMenu", "JoypadState", "getMouseX", "getMouseY", "getSoundManager" }) do
        _G[name] = MELensDashboardRegressionSaved[name]
    end
    MELensDashboardRegressionSaved = nil
end
