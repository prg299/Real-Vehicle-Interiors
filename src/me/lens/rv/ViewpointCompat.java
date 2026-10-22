package me.lens.rv;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;

/** Optional camera handoff. No Viewpoint code or compile-time dependency is included. */
public final class ViewpointCompat {
    private ViewpointCompat() {}

    // Resolve only on first use, after ZombieBuddy has loaded the enabled mods.
    private static final class CameraState {
        static final VarHandle ENABLED = findEnabled();

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
    }

    /** Read the public volatile flag on each draw so a camera toggle needs no restart. */
    public static boolean active() {
        VarHandle enabled = CameraState.ENABLED;
        return enabled != null && (boolean) enabled.getVolatile();
    }
}
