-- Durable historical package goldens, independent of the current generators.
-- Load both fixtures immediately after all production profiles, then this file.
-- Source/engine-double evidence only; no saved world or native input is simulated.
do
    local M, P = MELens, MELens.Parts
    local fixtures = assert(MELensProfileSaveContracts, "historical profile save fixtures not loaded")
    local versions = { "2.0.14", "2.0.20" }
    local profileFields = { "floorY", "vehicleScale", "seatId", "walkGrid", "legacySpotCount",
        "factoryRole", "factoryLayout", "factoryFloor", "waterTank", "fuelTank", "extraSeats" }
    local spotFields = { "wall", "length", "depth", "pieces", "cargo", "factory", "default", "seats" }
    local kitFields = { "width", "depth", "height", "capacity", "kind" }
    local tolerance = 0.00000001

    local function same(actual, expected, path)
        if type(actual) == "number" and type(expected) == "number" then
            check(actual == actual and expected == expected and math.abs(actual - expected) < tolerance,
                path .. " changed: " .. tostring(expected) .. " -> " .. tostring(actual))
            return
        end
        check(type(actual) == type(expected), path .. " changed type/value presence")
        if type(expected) ~= "table" then
            check(actual == expected, path .. " changed")
            return
        end
        for key, value in pairs(expected) do same(actual[key], value, path .. "." .. tostring(key)) end
        for key in pairs(actual) do check(expected[key] ~= nil, path .. " added key " .. tostring(key)) end
    end

    local function offsetFor(profile, index)
        local offsets = profile.looseSpotOffsets
        return offsets and offsets[tostring(index)] or nil
    end

    local function coordinate(actual, previous, offset, path)
        check(type(actual) == "number" and type(previous) == "number", path .. " missing coordinate")
        same(actual - previous, offset, path .. " released-anchor delta")
    end

    local currentCount = 0
    for script in pairs(M.Profiles) do
        currentCount = currentCount + 1
        check(fixtures["2.0.20"] and fixtures["2.0.20"].profiles[script],
            "current profile is absent from released 2.0.20 contract: " .. tostring(script))
    end
    check(currentCount == 203, "current save-contract coverage must include all 203 script aliases")

    for _, version in ipairs(versions) do
        local fixture = assert(fixtures[version], "missing profile save golden " .. version)
        check(fixture.schemaVersion == 1 and fixture.version == version and fixture.profileCount == 203,
            version .. " historical fixture metadata/coverage changed")
        local hasSourceHash = false
        for _ in pairs(fixture.sourceFiles or {}) do hasSourceHash = true; break end
        check(type(fixture.sourceFiles) == "table" and hasSourceHash,
            version .. " fixture lost historical source hashes")
        local expectedCount, correctionCount = 0, 0
        for script, previous in pairs(fixture.profiles) do
            expectedCount = expectedCount + 1
            local current = M.Profiles[script]
            check(current ~= nil, version .. " lost released script " .. script)
            for _, key in ipairs(profileFields) do same(current[key], previous[key], version .. ":" .. script .. "." .. key) end
            check(#current.spots == #previous.spots, version .. ":" .. script .. " changed released spot count/indices")
            for index, oldSpot in ipairs(previous.spots) do
                local spot, path = current.spots[index], version .. ":" .. script .. ".spots[" .. index .. "]"
                for _, key in ipairs(spotFields) do same(spot[key], oldSpot[key], path .. "." .. key) end
                same(spot.rise or 0, oldSpot.rise, path .. ".rise")
                same(P.piecesFor(spot), oldSpot.allowedPieces, path .. ".effectiveAllowedPieces")
                local offset = offsetFor(current, index)
                local dx, dz = offset and offset.x or 0, offset and offset.z or 0
                local corrected = script == "Base.90fordF350ambulance" and (index == 7 or index == 8)
                if corrected then
                    correctionCount = correctionCount + 1
                    check(offset ~= nil, path .. " lost explicit released loose-item anchor offset")
                    same(dx, 0, path .. ".offset.x")
                    same(dz, -.06, path .. ".offset.z")
                else
                    check(offset == nil, path .. " unexpected saved-anchor correction")
                end
                coordinate(spot.x, oldSpot.x, dx, path .. ".x")
                coordinate(spot.z, oldSpot.z, dz, path .. ".z")
            end
            for key, offset in pairs(current.looseSpotOffsets or {}) do
                check(type(key) == "string" and (key == "7" or key == "8")
                    and script == "Base.90fordF350ambulance", script .. " unqualified looseSpotOffsets entry")
                check(type(offset) == "table", script .. " malformed looseSpotOffsets entry")
                for axis in pairs(offset) do check(axis == "x" or axis == "z", script .. " unexpected offset axis") end
            end
            local shell, oldShell = current.shell, previous.shell
            check(type(shell) == "table" and #shell.models >= #oldShell.models,
                version .. ":" .. script .. " removed a released shell model")
            for index, model in ipairs(oldShell.models) do
                same(shell.models[index], model, version .. ":" .. script .. ".shell.models[" .. index .. "]")
            end
            for _, key in ipairs({ "entryModel", "entryDoor", "extraDoors" }) do
                same(shell[key], oldShell[key], version .. ":" .. script .. ".shell." .. key)
            end
        end
        check(expectedCount == 203, version .. " fixture does not enumerate exactly 203 released aliases")
        check(correctionCount == 2, version .. " must qualify exactly the two F350 medical front slots")
        for piece, previous in pairs(fixture.rvKit) do
            local current = M.RVKit[piece]
            check(current ~= nil, version .. " lost released furniture piece " .. piece)
            for _, key in ipairs(kitFields) do same(current[key], previous[key], version .. ":RVKit." .. piece .. "." .. key) end
        end
    end
end
