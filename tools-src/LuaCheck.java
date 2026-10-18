import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;
import se.krka.kahlua.j2se.J2SEPlatform;
import se.krka.kahlua.luaj.compiler.LuaCompiler;
import se.krka.kahlua.vm.KahluaTable;

/** Build check: compiles every .lua file under the given folders with the game's own Kahlua compiler. */
public final class LuaCheck {
    public static void main(String[] args) throws Exception {
        // Compiling only needs a table as the chunk environment, not the game's stdlib.
        KahluaTable env = J2SEPlatform.getInstance().newTable();
        int files = 0, failures = 0;
        for (String root : args) {
            List<Path> scripts;
            try (Stream<Path> walk = Files.walk(Path.of(root))) {
                scripts = walk.filter(p -> p.toString().endsWith(".lua")).sorted().toList();
            }
            for (Path script : scripts) {
                files++;
                String source = Files.readString(script, StandardCharsets.UTF_8);
                try {
                    LuaCompiler.loadstring(source, script.getFileName().toString(), env);
                } catch (Exception | Error failure) {
                    failures++;
                    System.out.println("LUA ERROR " + script + ": " + failure.getMessage());
                }
            }
        }
        System.out.println("lua files checked: " + files + ", errors: " + failures);
        System.exit(failures == 0 ? 0 : 1);
    }
}
