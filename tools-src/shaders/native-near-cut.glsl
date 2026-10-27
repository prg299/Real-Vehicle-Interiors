// Geometric face classification is computed before any discard in main.
// Stock box vans use one level for each whole wall instead of a rounded ramp
// that leaves triangular glass fragments at the rear corners.
vec3 meLensCutFaceNormal;
float meLensSourceNear = -1.0;
uniform vec4 MELensCutFront; // door-bay front, down-axis top, original full cab front, enabled

bool meLensFrontKept(vec3 p)
{
    return MELensCutFront.w > 0.5 && p.y > MELensCutFront.x
        && (p.z > MELensCutFront.y || p.y > MELensCutFront.z);
}

float meLensFlatNear(vec3 p, vec4 shape, vec2 camera)
{
    if(meLensSourceNear>=0.0)return meLensSourceNear;
    vec2 n = meLensCutFaceNormal.xy;
    float size = length(n);
    if (size < 0.000001) return 0.0;
    n /= size;
    vec2 offset = p.xy - 0.5 * (shape.xy + shape.zw);
    if (dot(n, offset) < 0.0) n = -n;
    return step(0.001, dot(n, camera));
}
