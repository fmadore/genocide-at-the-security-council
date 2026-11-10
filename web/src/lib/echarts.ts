/**
 * The chart engine, with only what the dashboard draws registered.
 *
 * A module of its own so that `Chart.svelte` can import it when the first
 * chart mounts rather than when its page does. ECharts is the heaviest thing
 * the site ships, and a page with no chart, or a reader who leaves before the
 * first plate, should not wait for it or pay for it.
 *
 * Registering only the series and components in use keeps the chunk
 * tree-shaken: bar, line and scatter series; the grid, tooltip, legend, zoom
 * and aria components; and both renderers, since the semantic map draws to a
 * canvas and every other figure to SVG.
 *
 * And the label-layout feature, without which every `labelLayout` on the site
 * (`moveOverlap` on the Chronology's end labels, `hideOverlap` on the
 * collocate scatter) was silently ignored: "genocide" was printed over the
 * wrapped "crimes against humanity" (review of 10 November 2026).
 */
import { BarChart, LineChart, ScatterChart } from 'echarts/charts';
import {
	AriaComponent,
	DataZoomComponent,
	GridComponent,
	LegendComponent,
	TooltipComponent
} from 'echarts/components';
import { init, use } from 'echarts/core';
import { LabelLayout } from 'echarts/features';
import { CanvasRenderer, SVGRenderer } from 'echarts/renderers';

use([
	BarChart,
	LineChart,
	ScatterChart,
	GridComponent,
	TooltipComponent,
	LegendComponent,
	DataZoomComponent,
	AriaComponent,
	LabelLayout,
	SVGRenderer,
	CanvasRenderer
]);

export { init };
