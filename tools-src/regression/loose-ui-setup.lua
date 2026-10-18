-- Load-time services for production LooseUI. These are engine doubles, not UI input evidence.
MELensLooseUISaved={ISUIElement=ISUIElement,events={}}
ISUIElement={}
function ISUIElement:derive(name)
    local child={Type=name};setmetatable(child,{__index=self});return child
end
for _,name in ipairs({"OnFillInventoryObjectContextMenu","OnGameStart","OnMainMenuEnter","OnPostUIDraw"}) do
    MELensLooseUISaved.events[name]=Events[name]
    Events[name]={Add=function() end}
end
