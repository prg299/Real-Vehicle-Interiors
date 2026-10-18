-- Developer test mod only: marks that the test endpoint mod is active in this profile.
print("[RealVehicleInteriors_Dev] developer test endpoint mod active (test profile only)")

-- The answer of the server's "eval" (42.21/media/lua/server/MELensDev_Server.lua): MELensDevResult = { id, text }.
Events.OnServerCommand.Add(function(module, command, args)
    if module == "MELensDev" and command == "result" and type(args) == "table" then
        MELensDevResult = { id = args.id, text = args.text }
    end
end)
