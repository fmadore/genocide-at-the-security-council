/**
 * Run a callback once, when an element has been reached on the page.
 *
 * Two mechanisms, because neither is enough on its own.
 *
 * The observer is the right primitive for "the plate came into view": it fires
 * when the content above the element grows or shrinks, which no scroll event
 * reports. Its one hole is the instant jump — a deep link to an anchor below
 * the element, or `scrollTo(0, scrollHeight)` — where the element goes from
 * below the window to above it between two frames and the ratio never leaves
 * zero, so no second callback is delivered. The passive listener closes that
 * hole by asking where the element is rather than waiting to be told.
 * Whichever wins, the callback runs once, and a browser with no observer at
 * all is left with the listener and the first-frame check.
 *
 * Reached, not visible: a reader who jumped past the element has reached it
 * just as surely as one who scrolled onto it, and something that refused to
 * load because the reader arrived too fast would be the worse bug.
 *
 * Written for the Actors map (MapLibre is fetched only here) and shared with
 * the Usage page, whose contested passages need two large files.
 *
 * @returns a function that stops watching without running the callback.
 */
export function onReached(element: Element, margin: number, callback: () => void): () => void {
	let done = false;
	const reached = () => element.getBoundingClientRect().top < window.innerHeight + margin;
	const fire = () => {
		if (done) return;
		stop();
		callback();
	};
	const check = () => {
		if (!done && reached()) fire();
	};
	const watcher =
		typeof IntersectionObserver === 'function'
			? new IntersectionObserver(
					(entries) => {
						if (entries.some((entry) => entry.isIntersecting)) fire();
					},
					{ rootMargin: `${margin}px` }
				)
			: null;
	function stop() {
		done = true;
		watcher?.disconnect();
		window.removeEventListener('scroll', check);
		window.removeEventListener('resize', check);
	}
	watcher?.observe(element);
	window.addEventListener('scroll', check, { passive: true });
	window.addEventListener('resize', check);
	// A window tall enough, or a link deep enough, and the element is already
	// here on the first frame.
	check();
	return stop;
}
