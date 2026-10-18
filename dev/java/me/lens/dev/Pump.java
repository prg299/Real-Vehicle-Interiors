package me.lens.dev;

import me.zed_0xff.zombie_buddy.Patch;

/** DEVELOPER TEST MOD ONLY. Runs queued test Lua once per UI update on the main thread. */
public final class Pump {
    private Pump() {}

    @Patch(className = "zombie.ui.UIManager", methodName = "update")
    public static final class UiUpdate {
        @Patch.OnExit
        public static void exit() {
            Main.runTasks();
        }
    }
}
