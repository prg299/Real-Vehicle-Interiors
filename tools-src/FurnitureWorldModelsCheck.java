import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import zombie.scripting.ScriptParser;

/** Checks drop-model contracts with the installed game's script parser; not native rendering evidence. */
public final class FurnitureWorldModelsCheck {
    private static final String[] PIECES = {"bed", "dinette", "kitchen", "fridge", "cabinet", "wardrobe",
        "washroom", "heater", "shelf", "box", "busseat", "busseat2"};

    private static Map<String, ScriptParser.Block> blocks(Path path, String type) throws Exception {
        var root = ScriptParser.parse(ScriptParser.stripComments(Files.readString(path, StandardCharsets.UTF_8)));
        var module = root.getBlock("module", "Base");
        if (module == null) throw new AssertionError("Missing Base module: " + path);
        var result = new HashMap<String, ScriptParser.Block>();
        for (var block : module.children) {
            if (type.equals(block.type) && result.put(block.id, block) != null) {
                throw new AssertionError("Duplicate " + type + ": " + block.id);
            }
        }
        return result;
    }

    private static String value(ScriptParser.Block block, String key) {
        if (block == null) throw new AssertionError("Missing script block for " + key);
        var value = block.getValue(key);
        return value == null ? null : value.getValue().trim();
    }

    private static void equal(Object expected, Object actual, String label) {
        if (!java.util.Objects.equals(expected, actual)) {
            throw new AssertionError(label + ": expected " + expected + ", found " + actual);
        }
    }

    public static void main(String[] args) throws Exception {
        Path media = Path.of(args[0]);
        var items = blocks(media.resolve("scripts/MELens_items.txt"), "item");
        var models = blocks(media.resolve("scripts/MELens_models.txt"), "model");
        for (String piece : PIECES) {
            String name = "MELensRV_" + piece;
            String itemName = "MELensRV_" + Character.toUpperCase(piece.charAt(0)) + piece.substring(1);
            var ground = models.get(name + "_ground");
            var installed = models.get(name);
            equal(name + "_ground", value(items.get(itemName), "WorldStaticModel"), itemName + " ground binding");
            equal(value(installed, "mesh"), value(ground, "mesh"), name + " shared mesh");
            equal(value(installed, "texture"), value(ground, "texture"), name + " shared texture");
            equal(null, value(ground, "shader"), name + " normal item shader");
            float groundScale = Float.parseFloat(value(ground, "scale"));
            float vehicleScale = Float.parseFloat(value(installed, "scale"));
            if (Math.abs(groundScale * 1.5f - vehicleScale * 0.9f) > 1.0e-7f) {
                throw new AssertionError(name + " ground/vehicle camera scales differ");
            }
            String mesh = value(ground, "mesh").split("\\|", 2)[0];
            if (!Files.isRegularFile(media.resolve("models_X/" + mesh + ".fbx"))) {
                throw new AssertionError(name + " mesh file missing");
            }
            if (!Files.isRegularFile(media.resolve("textures/" + value(ground, "texture") + ".png"))) {
                throw new AssertionError(name + " texture file missing");
            }
        }
        equal(null, value(items.get("MELensRV_Seat"), "WorldStaticModel"), "hidden standing marker");
        System.out.println("Furniture ground models: " + PIECES.length
            + " bindings, shared assets and scale contracts passed; native rendering remains separate.");
    }
}
