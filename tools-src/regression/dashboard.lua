-- Optional Neat preferences, live repaint and foreground readability. These are
-- production draw-call contracts; native settings/input review is separate.
do
    local saved = {}
    for _, key in ipairs({ "getActivatedMods", "getTexture", "NR_Config", "NC_UserConfig", "NCConfig",
            "NEQ_Style", "CleanUI_getBackgroundOpacity" }) do saved[key] = _G[key] end
    local enabled = {}
    getActivatedMods = function() return { contains = function(_, id) return enabled[id] == true end } end
    local function expect(body, title, card, label)
        local a, b, c = MELens.Dashboard.neatOpacities()
        check(math.abs(a-body) < 0.00001 and math.abs(b-title) < 0.00001 and math.abs(c-card) < 0.00001, label)
    end
    NR_Config, NC_UserConfig, NCConfig, NEQ_Style = nil, nil, nil, nil
    expect(.96, 1, 1, "no optional settings preserves the dashboard defaults")
    NR_Config = { bgAlpha = .3 }
    expect(.96, 1, 1, "disabled Rocco globals cannot restyle the dashboard")
    enabled.Neat_Rocco = true
    expect(.3, .3, .3, "Rocco background opacity applies to body title and cards")
    NR_Config.bgAlpha = .6
    expect(.6, .6, .6, "open dashboard reads live Rocco option changes")
    NR_Config.bgAlpha = 0
    expect(0, 0, 0, "zero opacity is a valid value")
    NR_Config.bgAlpha = 2
    expect(1, 1, 1, "out of range opacity is clamped")
    NR_Config.bgAlpha = -1
    expect(0, 0, 0, "negative opacity is clamped")
    NR_Config.bgAlpha = 0/0
    expect(.96, 1, 1, "invalid opacity cannot poison drawing")
    enabled = { Neat_Crafting = true }
    NCConfig = { windowBackgroundAlpha = .82, titleBackgroundAlpha = .88, innerBackgroundAlpha = .78 }
    NC_UserConfig = { getBackgroundAlpha = function(base) return base / 2 end,
        getTitleBarAlpha = function() return .7 end, getInnerPanelAlpha = function(base) return base / 2 end }
    expect(.41, .7, .39, "Crafting uses its own alpha resolvers and baseline surfaces")
    enabled.Neat_Rocco, NR_Config.bgAlpha = true, .5
    expect(.5, .5, .5, "vehicle window preferences take priority over Crafting")
    enabled.Neat_Rocco = false
    NC_UserConfig.getBackgroundAlpha = function() error("unavailable optional getter") end
    NC_UserConfig.getInnerPanelAlpha = function() return "invalid" end
    expect(.82, .7, .78, "failing or invalid optional getters retain safe surface defaults")
    NC_UserConfig = {}
    expect(.82, .88, .78, "older Crafting versions need no absent opacity functions")
    enabled, NEQ_Style = { NeatUI_Equipment = true }, { BODY_ALPHA = .4, LOOK = "neat" }
    expect(.4, 1, .4, "Equipment body opacity preserves its solid title convention")
    NEQ_Style.LOOK, CleanUI_getBackgroundOpacity = "cleanui", function() return .25 end
    expect(.25, .95, .25, "Equipment CleanUI option follows its chosen background source")
    check(MELensVanillaDashboard.neatOpacities == nil, "vanilla dashboard does not inherit Neat painting preferences")

    enabled, NR_Config = { Neat_Rocco = true }, { bgAlpha = .35 }
    getTexture = function(path) return path end
    local draws, texts = {}, {}
    local w = setmetatable({ width = 580, height = 250, title = "Dashboard", controls = {},
        closeBox = {x=530,y=8,w=24,h=24}, cards = {{x=14,y=54,w=268,h=120,title="Power",rows={},
            buttons={{x=26,y=125,w=80,h=26,enabled=true,text="Use"}}}} }, { __index = MELensDashboard })
    function w:getMouseX() return -1 end
    function w:getMouseY() return -1 end
    function w:drawRect(x,y,width,height,alpha,r,g,b)
        draws[#draws+1] = {x=x,y=y,w=width,h=height,a=alpha,r=r,g=g,b=b}
    end
    function w:drawTextureScaled(_,x,y,width,height,alpha,r,g,b) self:drawRect(x,y,width,height,alpha,r,g,b) end
    function w:drawText(_,_,_,_,_,_,alpha) texts[#texts+1] = alpha end
    w.drawTextCentre = w.drawText
    w:prerender(); w:render()
    local body, title, card, button, strip = false, false, false, false, 0
    for _, draw in ipairs(draws) do
        if draw.r == .105 then body = draw.a == .35 end
        if draw.r == .075 then
            title = draw.a == .35
            if 50 >= draw.x and 50 < draw.x+draw.w and 35 >= draw.y and 35 < draw.y+draw.h then strip = strip+1 end
        end
        if draw.r == .155 then card = draw.a == .35 end
        if draw.r == .235 then button = draw.a == 1 end
    end
    check(body and title and card, "Neat transparency reaches production background draw calls")
    check(strip == 1, "translucent title has no double-painted lower strip")
    check(button, "action buttons remain readable over a transparent panel")
    for _, alpha in ipairs(texts) do check(alpha == 1 or alpha == .6, "panel transparency does not fade labels or close glyph") end
    NR_Config.bgAlpha = .8
    w:prerender()
    check(w.cardOpacity == .8, "next frame applies changed preferences without reconstructing the window")
    for _, key in ipairs({ "getActivatedMods", "getTexture", "NR_Config", "NC_UserConfig", "NCConfig",
            "NEQ_Style", "CleanUI_getBackgroundOpacity" }) do _G[key] = saved[key] end
end

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
