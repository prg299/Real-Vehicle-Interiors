package me.lens.dev;

import me.zed_0xff.zombie_buddy.Exposer;
import zombie.iso.IsoChunk;
import zombie.iso.IsoGridSquare;
import zombie.iso.IsoWorld;
import zombie.network.ServerMap;
import zombie.vehicles.BaseVehicle;
import zombie.vehicles.VehiclesDB2;

/**
 * Developer test endpoint, server side (local test servers only, never shipped): spawns a vehicle the
 * way the game's own /addvehicle command does (AddVehicleCommand), for multiplayer tests. Tries rings
 * round the asked square until a place is free.
 */
@Exposer.LuaClass(name = "MELensDevSpawn")
public final class Spawn {
    private Spawn() {}

    public static String add(String script, int x0, int y0) {
        for (int r = 0; r <= 30; r += 3) {
            for (int dx = -r; dx <= r; dx += 3) {
                for (int dy : new int[] {-r, r}) {
                    String result = tryAt(script, x0 + dx, y0 + dy);
                    if (result.startsWith("ok")) {
                        return result;
                    }
                }
            }
        }
        return "no free place";
    }

    private static String tryAt(String script, int x, int y) {
        IsoGridSquare square = ServerMap.instance.getGridSquare(x, y, 0);
        if (square == null) {
            return "no square";
        }
        BaseVehicle v = new BaseVehicle(IsoWorld.instance.currentCell);
        v.setScriptName(script);
        v.setX(x - 1.0f);
        v.setY(y - 0.1f);
        v.setZ(0.2f);
        if (!IsoChunk.doSpawnedVehiclesInInvalidPosition(v)) {
            return "invalid";
        }
        v.setSquare(square);
        v.square.chunk.vehicles.add(v);
        v.chunk = v.square.chunk;
        v.addToWorld();
        VehiclesDB2.instance.addVehicle(v);
        v.setCurrentKey(v.createVehicleKey());
        v.repair();
        for (int i = 0; i < v.getPartCount(); i++) {
            if (v.getPartByIndex(i).getDoor() != null) {
                v.getPartByIndex(i).getDoor().setLocked(false);
            }
        }
        return "ok " + v.getId() + " at " + x + "," + y;
    }
}
