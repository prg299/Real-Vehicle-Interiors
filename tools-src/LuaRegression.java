import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import se.krka.kahlua.j2se.J2SEPlatform;
import se.krka.kahlua.luaj.compiler.LuaCompiler;
import se.krka.kahlua.vm.KahluaTable;
import se.krka.kahlua.vm.KahluaThread;

/** Executes production Lua with explicit engine doubles. This is not native/input evidence. */
public final class LuaRegression {
    public static void main(String[] args) throws Exception {
        var platform = J2SEPlatform.getInstance();
        KahluaTable env = platform.newTable();
        env.rawset("_G", env);
        se.krka.kahlua.stdlib.BaseLib.register(env);
        se.krka.kahlua.stdlib.TableLib.register(platform, env);
        se.krka.kahlua.stdlib.StringLib.register(platform, env);
        se.krka.kahlua.stdlib.CoroutineLib.register(platform, env);
        se.krka.kahlua.stdlib.OsLib.register(platform, env);
        se.krka.kahlua.stdlib.RandomLib.register(platform, env);
        se.krka.kahlua.j2se.MathLib.register(platform, env);
        var thread = new KahluaThread(platform, env);
        thread.debugOwnerThread = Thread.currentThread();
        se.krka.kahlua.vm.KahluaUtil.setWorkerThread(env, thread);
        se.krka.kahlua.vm.KahluaUtil.setupLibraryText(env, thread,
            Path.of(args[1], "stdlib.lua").toFile());
        Path root = Path.of(args[0]);
        String shared = "mod/RealVehicleInteriors/common/media/lua/shared/";
        String client = "mod/RealVehicleInteriors/common/media/lua/client/";
        for (String name : new String[] {
            "tools-src/regression/setup.lua", shared + "MELens_RVKit.lua",
            shared + "MELens_Profiles.lua", shared + "MELens_Profile_F700box.lua",
            shared + "MELens_WalkGrid_F700box_Shell.lua",
            shared + "MELens_Profile_B700.lua", shared + "MELens_WalkGrid_B700_Shell.lua",
            shared + "MELens_Parts.lua", shared + "MELens_Utilities.lua", shared + "TimedActions/MELens_Actions.lua",
            client + "MELens_Interact.lua", shared + "MELens_Sync.lua", shared + "MELens_Phobia.lua",
            "tools-src/regression/f700.lua", "tools-src/regression/phobia.lua", "tools-src/regression/checks.lua",
            "tools-src/regression/lifecycle.lua", shared + "MELens_Home.lua",
            "tools-src/regression/utilities.lua", "tools-src/regression/lamps.lua",
            "tools-src/regression/personalization.lua", "tools-src/regression/interior-actions.lua",
            "tools-src/regression/dashboard-setup.lua", client + "MELens_Dashboard.lua",
            "tools-src/regression/dashboard.lua", "tools-src/regression/loose-ui-setup.lua",
            client + "MELens_LooseUI.lua", "tools-src/regression/loose-ui.lua",
            client + "MELens_Bed.lua", "tools-src/regression/bed.lua",
            "tools-src/regression/standing.lua", "tools-src/regression/entry-setup.lua",
            "game:media/lua/client/Vehicles/TimedActions/ISEnterVehicle.lua",
            client + "MELens_Cabin.lua", "tools-src/regression/entry.lua"
        }) {
            if (name.endsWith("/MELens_Home.lua")) {
                var events = (KahluaTable) env.rawget("Events");
                for (String eventName : new String[] {"EveryOneMinute", "EveryTenMinutes"}) {
                    var event = platform.newTable();
                    var callbacks = platform.newTable();
                    event.rawset("callbacks", callbacks);
                    event.rawset("Add", (se.krka.kahlua.vm.JavaFunction) (frame, count) -> {
                        callbacks.rawset((double) callbacks.len() + 1, frame.get(0));
                        return 0;
                    });
                    events.rawset(eventName, event);
                }
            }
            Path source = name.startsWith("game:") ? Path.of(args[1], name.substring(5)) : root.resolve(name);
            var chunk = LuaCompiler.loadstring(Files.readString(source, StandardCharsets.UTF_8), name, env);
            Object[] result = thread.pcall(chunk, new Object[0]);
            if (!Boolean.TRUE.equals(result[0])) {
                throw new AssertionError(name + ": " + java.util.Arrays.toString(result));
            }
        }
        System.out.println("ME_LENS regression assertions=" + env.rawget("assertions")
            + " productionLua=true engineDoubles=true nativeInput=false");
    }
}
