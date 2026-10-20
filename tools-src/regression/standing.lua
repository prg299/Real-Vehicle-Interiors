-- Standing-seat lifecycle with engine doubles. Native combat/input is separate.
do
    local oldContainer, oldItem, oldClient = ItemContainer, instanceItem, isClient
    local made, client = 0, false
    ItemContainer = { new = function()
        local c = { contents = {} }
        function c:setType(value) self.kind = value end
        function c:setCapacity(value) self.capacity = value end
        function c:setExplored(value) self.explored = value end
        function c:setAcceptItemFunction(value) self.accept = value end
        function c:getCapacityWeight() return #self.contents end
        return c
    end }
    instanceItem = function(fullType) made = made + 1; return { fullType = fullType } end
    isClient = function() return client end
    local function part(container, item)
        local p = { container = container, item = item }
        function p:getId() return "SeatMELensCabin" end
        function p:getItemContainer() return self.container end
        function p:setItemContainer(value) self.container = value end
        function p:getInventoryItem() return self.item end
        function p:setInventoryItem(value) self.item = value end
        return p
    end

    -- This is the missing-container save state that crashed CombatManager.
    local p = part(nil, nil)
    MELens.initStandingPart(nil, p)
    local c, item = p.container, p.item
    check(c and c:getCapacityWeight() == 0, "standing seat still has no combat container")
    check(c.kind == p:getId() and c.capacity == 0 and c.explored, "repaired container has incorrect metadata")
    check(c.accept == "MELens.standingContainerTest" and not MELens.standingContainerTest(nil, p, nil),
        "standing container permits loot or item insertion")
    check(item and item.fullType == "Base.MELensRV_Seat" and made == 1, "server standing-seat item is missing")
    MELens.initStandingPart(nil, p)
    check(p.container == c and p.item == item and made == 1, "standing initialization replaced existing state")

    -- Even unexpected old contents must survive initialization.
    local savedItem = {}
    c.contents[1] = savedItem
    MELens.initStandingPart(nil, p)
    check(p.container == c and c.contents[1] == savedItem and c:getCapacityWeight() == 1,
        "standing initialization discarded saved contents")

    client = true
    p = part(nil, nil)
    MELens.initStandingPart(nil, p)
    check(p.container and p.container:getCapacityWeight() == 0, "client did not repair missing combat container")
    check(p.item == nil and made == 1, "client invented an authoritative seat item")
    local replicatedItem = {}
    p.item = replicatedItem
    MELens.initStandingPart(nil, p)
    check(p.item == replicatedItem and made == 1, "client replaced replicated seat item")
    ItemContainer, instanceItem, isClient = oldContainer, oldItem, oldClient
end
