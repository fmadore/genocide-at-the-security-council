<script lang="ts">
	import { tick } from 'svelte';
	let {
		label,
		options,
		value = $bindable(''),
		onchange = () => {}
	}: {
		label: string;
		options: { value: string; label: string }[];
		value?: string;
		onchange?: (value: string) => void;
	} = $props();
	const id = $props.id();
	let open = $state(false);
	let query = $state('');
	let active = $state(-1);
	let input: HTMLInputElement;
	const selectedLabel = $derived(options.find((option) => option.value === value)?.label ?? value);
	const matches = $derived(
		[{ value: '', label: 'All' }, ...options.filter((option) => option.value !== '')].filter(
			(option) =>
				`${option.label} ${option.value}`
					.toLocaleLowerCase()
					.includes(query.trim().toLocaleLowerCase())
		)
	);
	function choose(next: string) {
		value = next;
		onchange(next);
		open = false;
		query = '';
		active = -1;
	}
	function begin() {
		open = true;
		query = '';
		active = -1;
	}
	async function keyboard(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			open = false;
			active = -1;
			return;
		}
		if (event.key === 'Enter' && open && active >= 0 && matches[active]) {
			event.preventDefault();
			choose(matches[active].value);
			return;
		}
		if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
		event.preventDefault();
		if (!open) begin();
		active = Math.max(
			0,
			Math.min(matches.length - 1, active + (event.key === 'ArrowDown' ? 1 : -1))
		);
		await tick();
		document.getElementById(`${id}-${active}`)?.scrollIntoView({ block: 'nearest' });
	}
</script>

<div class="search-select">
	<label for={id}>{label}</label>
	<input
		bind:this={input}
		{id}
		role="combobox"
		aria-autocomplete="list"
		aria-expanded={open}
		aria-controls={`${id}-list`}
		aria-activedescendant={open && active >= 0 && matches[active] ? `${id}-${active}` : undefined}
		value={open ? query : selectedLabel}
		placeholder="All — type to search"
		onfocus={begin}
		onclick={() => {
			if (!open) begin();
		}}
		oninput={(event) => {
			query = event.currentTarget.value;
			open = true;
			active = -1;
		}}
		onkeydown={keyboard}
		onblur={() => {
			open = false;
			active = -1;
		}}
		autocomplete="off"
	/>
	{#if open}
		<div class="choices">
			<ul id={`${id}-list`} role="listbox" aria-label={label}>
				{#each matches as option, index (option.value)}
					<li role="presentation">
						<button
							id={`${id}-${index}`}
							role="option"
							aria-selected={option.value === value}
							class:active={index === active}
							type="button"
							tabindex="-1"
							onmousedown={(event) => event.preventDefault()}
							onclick={() => {
								choose(option.value);
								input.focus();
								open = false;
							}}>{option.label}</button
						>
					</li>
				{/each}
			</ul>
			{#if !matches.length}<p role="status">No matching options.</p>{/if}
		</div>
	{/if}
</div>

<style>
	.search-select {
		position: relative;
		min-width: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
	}
	label {
		display: block;
	}
	input {
		width: 100%;
		min-width: 0;
	}
	.choices {
		position: absolute;
		z-index: 30;
		width: 100%;
		min-width: 12rem;
		max-width: calc(100vw - 2rem);
		background: var(--paper);
		border: 1px solid var(--rule-strong);
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		max-height: 16rem;
		overflow-y: auto;
	}
	button {
		width: 100%;
		text-align: left;
		padding: 0.5rem;
		border: 0;
		background: transparent;
		white-space: normal;
		overflow-wrap: anywhere;
	}
	.active,
	li:hover {
		background: var(--mark);
	}
	[aria-selected='true'] {
		font-weight: 700;
	}
	p {
		margin: 0.5rem;
	}
</style>
