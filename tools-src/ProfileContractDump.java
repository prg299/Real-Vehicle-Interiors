import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import se.krka.kahlua.j2se.J2SEPlatform;
import se.krka.kahlua.luaj.compiler.LuaCompiler;
import se.krka.kahlua.vm.KahluaTable;
import se.krka.kahlua.vm.KahluaThread;

/** Exports portable historical save contracts by evaluating the actual packaged Lua.
 * Engine doubles only; never opens a save or exports dependency/game assets.
 * Usage: ProfileContractDump repoRoot gameRoot historicalPackageRoot version output.lua
 */
public final class ProfileContractDump {
    private static final int EXPECTED_PROFILES = 203;
    private static final String[] PROFILE_FIELDS = {"floorY", "vehicleScale", "seatId", "walkGrid",
        "legacySpotCount", "factoryRole", "factoryLayout", "factoryFloor", "waterTank", "fuelTank", "extraSeats"};
    private static final String[] SPOT_FIELDS = {"wall", "x", "z", "length", "depth", "pieces",
        "cargo", "factory", "default", "seats"};
    private static final String[] KIT_FIELDS = {"width", "depth", "height", "capacity", "kind"};

    private ProfileContractDump() {}

    private static void eval(KahluaThread thread, KahluaTable env, Path source) throws Exception {
        Object[] result = thread.pcall(LuaCompiler.loadstring(
            Files.readString(source, StandardCharsets.UTF_8), source.getFileName().toString(), env), new Object[0]);
        if (!Boolean.TRUE.equals(result[0])) throw new IllegalStateException(source + ": " + java.util.Arrays.toString(result));
    }

    private static KahluaTable table(Object value, String name) {
        if (!(value instanceof KahluaTable result)) throw new IllegalStateException("Missing table: " + name);
        return result;
    }

    private static String hash(Path path) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
    }

    private static Object value(Object raw) {
        if (raw == null || raw instanceof String || raw instanceof Boolean) return raw;
        if (raw instanceof Number number) {
            if (!Double.isFinite(number.doubleValue())) throw new IllegalStateException("Nonfinite contract number");
            return number.doubleValue();
        }
        KahluaTable source = table(raw, "contract value");
        int count = 0, length = source.len();
        boolean array = true;
        var iterator = source.iterator();
        while (iterator.advance()) {
            count++;
            Object key = iterator.getKey();
            if (!(key instanceof Number number) || number.doubleValue() != Math.rint(number.doubleValue())
                    || number.doubleValue() < 1 || number.doubleValue() > length) array = false;
        }
        if (array && count == length && count > 0) {
            List<Object> result = new ArrayList<>();
            for (int i = 1; i <= length; i++) result.add(value(source.rawget((double) i)));
            return result;
        }
        Map<String, Object> result = new TreeMap<>();
        iterator = source.iterator();
        while (iterator.advance()) {
            if (!(iterator.getKey() instanceof String key)) throw new IllegalStateException("Unexpected nonstring map key");
            result.put(key, value(iterator.getValue()));
        }
        return result;
    }

    private static Map<String, Object> select(KahluaTable source, String[] fields) {
        Map<String, Object> result = new TreeMap<>();
        for (String field : fields) if (source.rawget(field) != null) result.put(field, value(source.rawget(field)));
        return result;
    }

    private static List<Object> array(Object raw, String name) {
        KahluaTable source = table(raw, name);
        List<Object> result = new ArrayList<>();
        for (int i = 1; i <= source.len(); i++) result.add(value(source.rawget((double) i)));
        return result;
    }

    private static String quote(String source) {
        StringBuilder result = new StringBuilder("\"");
        for (char c : source.toCharArray()) {
            switch (c) {
                case '\\' -> result.append("\\\\");
                case '"' -> result.append("\\\"");
                case '\n' -> result.append("\\n");
                case '\r' -> result.append("\\r");
                case '\t' -> result.append("\\t");
                default -> {
                    if (c < 32 || c == 127) result.append(String.format("\\%03d", (int) c));
                    else result.append(c);
                }
            }
        }
        return result.append('"').toString();
    }

    private static String lua(Object object, int level) {
        if (object == null) return "nil";
        if (object instanceof String string) return quote(string);
        if (object instanceof Boolean || object instanceof Number) return object.toString();
        String pad = "  ".repeat(level), childPad = pad + "  ";
        List<String> rows = new ArrayList<>();
        if (object instanceof Map<?, ?> map) {
            for (var entry : map.entrySet()) rows.add(childPad + "[" + quote(entry.getKey().toString()) + "] = "
                + lua(entry.getValue(), level + 1) + ",");
        } else if (object instanceof List<?> list) {
            for (Object item : list) rows.add(childPad + lua(item, level + 1) + ",");
        } else throw new IllegalStateException("Unsupported contract type: " + object.getClass());
        return rows.isEmpty() ? "{}" : "{\n" + String.join("\n", rows) + "\n" + pad + "}";
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 5) throw new IllegalArgumentException(
            "Usage: ProfileContractDump repoRoot gameRoot historicalPackageRoot version output.lua");
        Path root = Path.of(args[0]).toAbsolutePath().normalize(), game = Path.of(args[1]);
        Path pack = Path.of(args[2]).toAbsolutePath().normalize(), output = Path.of(args[4]);
        if (Files.exists(output)) throw new IllegalStateException("Refusing to overwrite historical golden: " + output);
        Path shared = pack.resolve("common/media/lua/shared");
        if (!Files.isDirectory(shared)) shared = pack.resolve("mod/RealVehicleInteriors/common/media/lua/shared");
        if (!Files.isDirectory(shared)) throw new IllegalStateException("Package shared Lua directory absent: " + pack);

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
        se.krka.kahlua.vm.KahluaUtil.setupLibraryText(env, thread, game.resolve("stdlib.lua").toFile());
        Path setup = root.resolve("tools-src/regression/setup.lua");
        eval(thread, env, setup);
        List<Path> sources = new ArrayList<>();
        sources.add(shared.resolve("MELens_RVKit.lua"));
        sources.add(shared.resolve("MELens_Java.lua"));
        sources.add(shared.resolve("MELens_Profiles.lua"));
        try (var stream = Files.list(shared)) {
            sources.addAll(stream.filter(path -> path.getFileName().toString().startsWith("MELens_Profile_")
                && path.toString().endsWith(".lua")).sorted().toList());
        }
        sources.add(shared.resolve("MELens_Parts.lua"));
        for (Path source : sources) eval(thread, env, source);
        KahluaTable melens = table(env.rawget("MELens"), "MELens");
        KahluaTable parts = table(melens.rawget("Parts"), "Parts");
        KahluaTable profiles = table(melens.rawget("Profiles"), "Profiles");
        Map<String, Object> contracts = new TreeMap<>();
        var iterator = profiles.iterator();
        while (iterator.advance()) {
            String script = (String) iterator.getKey();
            KahluaTable profile = table(iterator.getValue(), script);
            Map<String, Object> contract = select(profile, PROFILE_FIELDS);
            KahluaTable spots = table(profile.rawget("spots"), script + ".spots");
            List<Object> spotContracts = new ArrayList<>();
            for (int i = 1; i <= spots.len(); i++) {
                KahluaTable spot = table(spots.rawget((double) i), script + ".spots[" + i + "]");
                Map<String, Object> row = select(spot, SPOT_FIELDS);
                row.put("rise", spot.rawget("rise") == null ? 0d : value(spot.rawget("rise")));
                Object[] allowed = thread.pcall(parts.rawget("piecesFor"), new Object[] {spot});
                if (!Boolean.TRUE.equals(allowed[0])) throw new IllegalStateException(script + ": piecesFor failed");
                row.put("allowedPieces", array(allowed[1], "allowed pieces"));
                spotContracts.add(row);
            }
            contract.put("spots", spotContracts);
            KahluaTable shell = table(profile.rawget("shell"), script + ".shell");
            Map<String, Object> shellContract = select(shell, new String[] {"entryModel", "entryDoor", "extraDoors"});
            shellContract.put("models", array(shell.rawget("models"), script + ".shell.models"));
            contract.put("shell", shellContract);
            contracts.put(script, contract);
        }
        if (contracts.size() != EXPECTED_PROFILES) throw new IllegalStateException(
            "Expected " + EXPECTED_PROFILES + " historical scripts, got " + contracts.size());
        Map<String, Object> kits = new TreeMap<>();
        iterator = table(melens.rawget("RVKit"), "RVKit").iterator();
        while (iterator.advance()) kits.put((String) iterator.getKey(), select(table(iterator.getValue(), "kit"), KIT_FIELDS));
        Map<String, Object> sourceHashes = new TreeMap<>();
        Path common = shared.getParent().getParent().getParent();
        for (Path source : sources) sourceHashes.put("common/" + common.relativize(source).toString().replace('\\', '/'), hash(source));
        Map<String, Object> fixture = new TreeMap<>();
        fixture.put("schemaVersion", 1d);
        fixture.put("version", args[3]);
        fixture.put("profileCount", (double) contracts.size());
        fixture.put("sourceFiles", sourceHashes);
        fixture.put("engineDoublesSha256", hash(setup));
        fixture.put("scope", "Historical packaged Lua save identities and placement contracts; no native/save execution");
        fixture.put("rvKit", kits);
        fixture.put("profiles", contracts);
        Files.createDirectories(output.toAbsolutePath().getParent());
        Files.writeString(output, "-- Historical golden; generated by ProfileContractDump from packaged production Lua.\n"
            + "MELensProfileSaveContracts = MELensProfileSaveContracts or {}\n"
            + "MELensProfileSaveContracts[" + quote(args[3]) + "] = " + lua(fixture, 0) + "\n"
            + "return MELensProfileSaveContracts[" + quote(args[3]) + "]\n", StandardCharsets.UTF_8);
        System.out.println("Historical profile contracts: version=" + args[3] + " scripts=" + contracts.size()
            + " sources=" + sources.size() + " output=" + output.toAbsolutePath());
    }
}
