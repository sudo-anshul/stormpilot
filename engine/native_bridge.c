/* Read-only instrumentation for pinned EPA SWMM 5.2.4.
 * SWMM's internal hydraulic volumes use cubic feet, including for SI inputs.
 * No solver equations or physical states are changed by this bridge.
 */
#include "headers.h"
extern TNodeStats *NodeStats;

double stormpilot_time_seconds(void) { return NewRoutingTime / 1000.0; }
double stormpilot_duration_seconds(void) { return TotalDuration / 1000.0; }
double stormpilot_node_flood_volume_m3(int index) {
    if (!NodeStats || index < 0 || index >= Nobjects[NODE]) return 0.0;
    return NodeStats[index].volFlooded * 0.028316846592;
}
double stormpilot_node_overflow_m3s(int index) {
    if (index < 0 || index >= Nobjects[NODE]) return 0.0;
    return Node[index].overflow * 0.028316846592;
}
double stormpilot_node_volume_m3(int index) {
    if (index < 0 || index >= Nobjects[NODE]) return 0.0;
    return Node[index].newVolume * 0.028316846592;
}
double stormpilot_link_flow_m3s(int index) {
    if (index < 0 || index >= Nobjects[LINK]) return 0.0;
    return Link[index].newFlow * 0.028316846592;
}
double stormpilot_link_volume_m3(int index) {
    if (index < 0 || index >= Nobjects[LINK]) return 0.0;
    return Link[index].newVolume * 0.028316846592;
}
