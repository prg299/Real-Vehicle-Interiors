package me.lens.rv;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodType;
import java.lang.invoke.VarHandle;
import zombie.characters.IsoGameCharacter;

/** Optional camera handoff. No Viewpoint code or compile-time dependency is included. */
public final class ViewpointCompat {
    private ViewpointCompat() {}

    // Resolve only on first use, after ZombieBuddy has loaded the enabled mods.
    private static final class CameraState {
        static final VarHandle ENABLED = findEnabled();
        static final MethodHandle SWITCH = findSwitch();
        static boolean switchFailed;

        private static VarHandle findEnabled() {
            try {
                Class<?> view = Class.forName("viewpoint.core.View", false, ViewpointCompat.class.getClassLoader());
                return MethodHandles.publicLookup().findStaticVarHandle(view, "enabled", boolean.class);
            } catch (ClassNotFoundException absent) {
                return null;
            } catch (ReflectiveOperationException | LinkageError | SecurityException unavailable) {
                System.err.println("[RealVehicleInteriors] Viewpoint camera-state API unavailable: " + unavailable);
                return null;
            }
        }

        private static MethodHandle findSwitch() {
            if (ENABLED == null) return null;
            try {
                Class<?> fp = Class.forName("viewpoint.FP", false, ViewpointCompat.class.getClassLoader());
                // Viewpoint 0.1.6.1 has no public set-view API. Use its own transition,
                // which clears camera caches and resets look state, rather than writing enabled.
                return MethodHandles.privateLookupIn(fp, MethodHandles.lookup()).findStatic(fp, "switchView",
                        MethodType.methodType(void.class, IsoGameCharacter.class, boolean.class));
            } catch (ReflectiveOperationException | LinkageError | SecurityException unavailable) {
                System.err.println("[RealVehicleInteriors] Viewpoint camera-switch API unavailable: " + unavailable);
                return null;
            }
        }
    }

    /** Read the public volatile flag on each draw so a camera toggle needs no restart. */
    public static boolean active() {
        VarHandle enabled = CameraState.ENABLED;
        return enabled != null && (boolean) enabled.getVolatile();
    }

    /** Main-thread only, for the local occupant of a walk-in interior (never a driver's seat). */
    public static boolean useIsometric(IsoGameCharacter player) {
        if (player == null || !active()) return false;
        MethodHandle change = CameraState.SWITCH;
        if (change == null || CameraState.switchFailed) return false;
        try {
            change.invokeExact(player, false);
            return !active();
        } catch (Throwable failure) {
            CameraState.switchFailed = true;
            System.err.println("[RealVehicleInteriors] Viewpoint camera handoff failed: " + failure);
            return false;
        }
    }
}
