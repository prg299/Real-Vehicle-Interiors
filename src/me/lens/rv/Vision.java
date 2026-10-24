package me.lens.rv;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.joml.Vector3f;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoPlayer;
import zombie.characters.IsoZombie;
import zombie.iso.IsoMovingObject;
import zombie.network.GameClient;
import zombie.vehicles.BaseVehicle;
import zombie.vehicles.VehiclePart;

/** Additional horizontal wall occlusion for registered physical interiors.
 * Native spotting still owns lighting, direction, distance and probability;
 * native sound, target memory, pathfinding and attacks are never rewritten. */
public final class Vision {
    private static final Map<String, Hull> HULLS = new ConcurrentHashMap<>();
    private static final ThreadLocal<Vector3f[]> VECTORS = ThreadLocal.withInitial(
            () -> new Vector3f[] { new Vector3f(), new Vector3f() });
    // Test-only reflection can disable this additive check for a native control.
    static volatile boolean enabled = true;
    private static final float EPS = .0001f;
    private static final float SKIN = .5f;

    private Vision() {}

    public static void register(String name, String outline, String openings) {
        if (name == null || name.isBlank() || outline == null || openings == null
                || outline.length() > 100_000 || openings.length() > 100_000) {
            throw new IllegalArgumentException("Invalid interior sight metadata");
        }
        String[] points = outline.split(";");
        if (points.length < 3) throw new IllegalArgumentException("Missing sight hull");
        float[] ring = new float[points.length * 2];
        for (int i = 0; i < points.length; i++) {
            String[] xy = points[i].split(",");
            if (xy.length != 2) throw new IllegalArgumentException("Invalid sight point");
            ring[i * 2] = number(xy[0]); ring[i * 2 + 1] = number(xy[1]);
        }
        List<Opening> ports = new ArrayList<>();
        if (!openings.isEmpty()) for (String row : openings.split(";")) {
            String[] v = row.split(",");
            if (v.length != 6 || v[0].isBlank() || !(v[1].equals("door") || v[1].equals("window"))) {
                throw new IllegalArgumentException("Invalid sight opening");
            }
            float x1 = number(v[2]), x2 = number(v[3]), z1 = number(v[4]), z2 = number(v[5]);
            if (x2 < x1 || z2 < z1) throw new IllegalArgumentException("Reversed sight bounds");
            ports.add(new Opening(v[0], v[1].equals("door"), x1, x2, z1, z2));
        }
        // Publish only a complete immutable registration. A bad replacement cannot
        // leave a partially built hull active on the zombie-owning client/server.
        HULLS.put(name, new Hull(ring, List.copyOf(ports)));
    }

    private static float number(String text) {
        float value = Float.parseFloat(text);
        if (!Float.isFinite(value) || Math.abs(value) > 1000) throw new IllegalArgumentException("Invalid sight coordinate");
        return value;
    }

    public static boolean blocksSight(IsoZombie observer, IsoMovingObject target) {
        if (!enabled || observer == null || !(target instanceof IsoPlayer player)
                || (GameClient.client && observer.isRemoteZombie()) || !Phobia.isEnclosed(player)) return false;
        BaseVehicle vehicle = player.getVehicle();
        if (observer.getVehicle() == vehicle || (int)Math.floor(observer.getZ()) != (int)Math.floor(player.getZ())) return false;
        Hull hull = HULLS.get(vehicle.getScript().getFullName());
        if (hull == null) return false;
        Vector3f[] vectors = VECTORS.get();
        Vector3f inside = vehicle.getPassengerLocalPos(vehicle.getSeat(player), vectors[0]);
        Vector3f outside = vehicle.getLocalPos(observer.getX(), observer.getY(), observer.getZ(), vectors[1]);
        Vector3f origin = vehicle.getScript().getModel().getOffset();
        return hull.blocks(vehicle, inside.x - origin.x, inside.z - origin.z,
                outside.x - origin.x, outside.z - origin.z);
    }

    /** Read-only observation used by the isolated native test harness. */
    public static String info(IsoZombie observer, IsoGameCharacter target) {
        boolean enclosed = Phobia.isEnclosed(target);
        BaseVehicle v = target == null ? null : target.getVehicle();
        String profile = v == null || v.getScript() == null ? "" : v.getScript().getFullName();
        return "{\"enclosed\":" + enclosed + ",\"registered\":" + HULLS.containsKey(profile)
                + ",\"blocked\":" + blocksSight(observer, target) + ",\"profile\":\"" + profile + "\"}";
    }

    record Opening(String part, boolean door, float x1, float x2, float z1, float z2) {
        boolean facesWall(float edgeX, float edgeZ) {
            boolean side = part.endsWith("Left") || part.endsWith("Right") || x2 - x1 < z2 - z1;
            if (part.startsWith("Windshield") || part.equals("TrunkDoor") || part.equals("DoorRear")) side = false;
            // A nearby cab window cannot open the perpendicular cargo divider.
            // The ring's tangent identifies which wall the ray actually crossed.
            return side ? Math.abs(edgeZ) >= Math.abs(edgeX) : Math.abs(edgeX) >= Math.abs(edgeZ);
        }

        boolean clear(BaseVehicle vehicle) {
            VehiclePart p = vehicle.getPartById(part);
            if (p == null) return false;
            // Intact glass transmits sight too. A removed window remains a hole;
            // an opaque door only does so while open, removed or destroyed.
            return door ? p.getDoor() != null && (p.getInventoryItem() == null || p.getCondition() <= 0
                    || p.getDoor().isOpen()) : p.getWindow() != null;
        }

        float intersection(float x, float z, float dx, float dz) {
            return intersection(x, z, dx, dz, 0);
        }

        float intersection(float x, float z, float dx, float dz, float nearestTo) {
            float lo = 0, hi = 1;
            if (Math.abs(dx) < EPS) {
                if (x < x1 - .025f || x > x2 + .025f) return -1;
            } else {
                float a = (x1 - .025f - x) / dx, b = (x2 + .025f - x) / dx;
                lo = Math.max(lo, Math.min(a, b)); hi = Math.min(hi, Math.max(a, b));
            }
            if (Math.abs(dz) < EPS) {
                if (z < z1 - .025f || z > z2 + .025f) return -1;
            } else {
                float a = (z1 - .025f - z) / dz, b = (z2 + .025f - z) / dz;
                lo = Math.max(lo, Math.min(a, b)); hi = Math.min(hi, Math.max(a, b));
            }
            // Interaction areas can be wide exterior rectangles. Measure from
            // their nearest intersected point, not their midpoint, to the wall.
            return lo <= hi ? Math.max(lo, Math.min(hi, nearestTo)) : -1;
        }
    }

    record Hull(float[] ring, List<Opening> openings) {
        boolean contains(float x, float z) {
            boolean inside = false;
            for (int i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
                float ax = ring[i], az = ring[i + 1], bx = ring[j], bz = ring[j + 1];
                if ((az > z) != (bz > z) && x < (bx - ax) * (z - az) / (bz - az) + ax) inside = !inside;
            }
            return inside;
        }

        boolean blocks(BaseVehicle vehicle, float x, float z, float ox, float oz) {
            if (!contains(x, z) || contains(ox, oz)) return false;
            float dx = ox - x, dz = oz - z, length = (float)Math.hypot(dx, dz);
            for (int i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
                float ax = ring[j], az = ring[j + 1], ex = ring[i] - ax, ez = ring[i + 1] - az;
                float cross = dx * ez - dz * ex;
                if (Math.abs(cross) < EPS) continue;
                float t = ((ax - x) * ez - (az - z) * ex) / cross;
                float u = ((ax - x) * dz - (az - z) * dx) / cross;
                if (t <= EPS || t > 1 || u < -EPS || u > 1 + EPS) continue;
                boolean clear = false;
                for (Opening port : openings) {
                    if (!port.facesWall(ex, ez)) continue;
                    float at = port.intersection(x, z, dx, dz, t);
                    if (at >= 0 && Math.abs(at - t) * length <= SKIN && port.clear(vehicle)) {
                        clear = true; break;
                    }
                }
                if (!clear) return true;
            }
            return false;
        }
    }
}
