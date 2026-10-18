-- Developer test driver: the rule that a piece cannot go where it would overlap what stands
-- next to it (MELens.Parts.roomFor), checked on every profile's data without any vehicle:
-- with the default layout standing, take each spot's piece out and ask which pieces could
-- go back in. The default piece must always be allowed (or a player could not put it back).
local P = MELens.Parts
local lines, problems = {}, 0
local seen = {}
local names = {}
for full, profile in pairs(MELens.Profiles) do
    if not seen[profile] then
        seen[profile] = true
        names[#names + 1] = { full = full, profile = profile }
    end
end
table.sort(names, function(a, b) return a.full < b.full end)
for _, entry in ipairs(names) do
    local profile = entry.profile
    local standing = {}
    for index, spot in ipairs(profile.spots) do
        if spot.default and not spot.empty then standing[index] = spot.default end
    end
    local blockedCount, allowedCount, defaultBlocked = 0, 0, {}
    local detail = {}
    for index, spot in ipairs(profile.spots) do
        local without = {}
        for i, piece in pairs(standing) do if i ~= index then without[i] = piece end end
        local allowed, blocked = {}, {}
        for _, piece in ipairs(P.PIECES) do
            if P.fits(spot, piece) and (not spot.level or not spot._under) then
                if P.roomFor(profile, without, index, piece) then
                    allowed[#allowed + 1] = piece
                    allowedCount = allowedCount + 1
                else
                    blocked[#blocked + 1] = piece
                    blockedCount = blockedCount + 1
                end
            end
        end
        if spot.default and not spot.empty and not P.roomFor(profile, without, index, spot.default) then
            defaultBlocked[#defaultBlocked + 1] = index .. ":" .. spot.default
            problems = problems + 1
        end
        if #blocked > 0 and #profile.spots <= 12 then
            detail[#detail + 1] = string.format("spot %d %s(%s) blocked: %s", index, tostring(spot.default), spot.wall, table.concat(blocked, ","))
        end
    end
    lines[#lines + 1] = string.format("%s: %d spots, %d placements allowed, %d blocked by a neighbour%s%s", entry.full, #profile.spots,
        allowedCount, blockedCount, #defaultBlocked > 0 and ("; DEFAULT BLOCKED " .. table.concat(defaultBlocked, " ")) or "",
        #detail > 0 and ("\n    " .. table.concat(detail, "\n    ")) or "")
end
lines[#lines + 1] = "default pieces that could not go back: " .. problems
return table.concat(lines, "\n")
