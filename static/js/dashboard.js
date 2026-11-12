const form = document.getElementById('analysisForm');
const button = document.getElementById('analyzeButton');
const statusBox = document.getElementById('status');

const searchInput = document.getElementById('locationSearch');
const suggestions = document.getElementById('suggestions');

let selectedLocation = null;
let geocodeTimer = null;
let geocodeController = null;
let analysisController = null;
let activeSuggestionIndex = -1;
let currentSuggestions = [];


function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[character]));
}


function clearSelectedLocation() {

    selectedLocation = null;

    document.getElementById('region').value = '';
    document.getElementById('latitude').value = '';
    document.getElementById('longitude').value = '';

    document.getElementById('locationHint').textContent =
        'Select a location from the suggestions. Coordinates are detected automatically.';
}


function hideSuggestions() {

    suggestions.style.display = 'none';
    activeSuggestionIndex = -1;
}


function showMessage(message) {

    suggestions.innerHTML =
        `<div class="suggestion">${escapeHtml(message)}</div>`;

    suggestions.style.display = 'block';
}


function selectLocation(place) {

    selectedLocation = place;

    searchInput.value = place.short_name;

    document.getElementById('region').value =
        place.short_name;

    document.getElementById('latitude').value =
        place.latitude;

    document.getElementById('longitude').value =
        place.longitude;

    document.getElementById('locationHint').textContent =
        `Selected: ${place.short_name}. Coordinates detected automatically.`;

    hideSuggestions();
}


function renderLocationSuggestions(results) {

    currentSuggestions = results;
    activeSuggestionIndex = -1;

    if (!results.length) {
        showMessage('No matching locations found. Try another spelling.');
        return;
    }

    suggestions.innerHTML = results.map((place, index) => {

        const details = [
            place.city,
            place.state,
            place.country
        ].filter(Boolean).join(', ');

        return `
            <div class="suggestion" data-index="${index}">
                <strong>${escapeHtml(place.name)}</strong>
                <small>${escapeHtml(details || place.short_name)}</small>
            </div>
        `;

    }).join('');

    suggestions.querySelectorAll('.suggestion[data-index]')
        .forEach(element => {

            element.addEventListener('click', () => {

                const index = Number(element.dataset.index);

                selectLocation(currentSuggestions[index]);

            });

        });

    suggestions.style.display = 'block';
}


async function searchLocations(query) {

    if (query.length < 2) {
        hideSuggestions();
        return;
    }

    if (geocodeController) {
        geocodeController.abort();
    }

    geocodeController = new AbortController();

    const controller = geocodeController;

    showMessage('Searching worldwide locations...');

    try {

        const response = await fetch(
            '/api/geocode?q=' + encodeURIComponent(query),
            { signal: controller.signal }
        );

        const data = await response.json();

        if (controller !== geocodeController) {
            return;
        }

        if (!response.ok) {
            throw new Error(
                data.error || 'Location search failed.'
            );
        }

        renderLocationSuggestions(data.results || []);

    } catch (error) {

        if (error.name === 'AbortError') {
            return;
        }

        showMessage(error.message);
    }
}


// Search automatically while the user types.
searchInput.addEventListener('input', () => {

    clearSelectedLocation();

    clearTimeout(geocodeTimer);

    if (geocodeController) {
        geocodeController.abort();
    }

    const query = searchInput.value.trim();

    if (query.length < 2) {
        hideSuggestions();
        return;
    }

    // Debounce requests to reduce unnecessary API traffic.
    geocodeTimer = setTimeout(() => {
        searchLocations(query);
    }, 350);

});


// Keyboard navigation inside the suggestion list.
searchInput.addEventListener('keydown', event => {

    const items = suggestions.querySelectorAll(
        '.suggestion[data-index]'
    );

    if (event.key === 'ArrowDown' && items.length) {

        event.preventDefault();

        activeSuggestionIndex = Math.min(
            activeSuggestionIndex + 1,
            items.length - 1
        );

    } else if (event.key === 'ArrowUp' && items.length) {

        event.preventDefault();

        activeSuggestionIndex = Math.max(
            activeSuggestionIndex - 1,
            0
        );

    } else if (event.key === 'Enter' && items.length) {

        event.preventDefault();

        if (activeSuggestionIndex >= 0) {
            selectLocation(
                currentSuggestions[activeSuggestionIndex]
            );
        }

        return;

    } else if (event.key === 'Escape') {

        hideSuggestions();
        return;
    }

    items.forEach((item, index) => {

        item.classList.toggle(
            'active',
            index === activeSuggestionIndex
        );

    });

});


document.addEventListener('click', event => {

    if (!event.target.closest('#locationSearch') &&
        !event.target.closest('#suggestions')) {

        hideSuggestions();
    }

});


function getNested(object, path) {

    return path.split('.').reduce(
        (value, key) =>
            value && value[key] !== undefined
                ? value[key]
                : undefined,
        object
    );
}


function firstValue(object, paths) {

    for (const path of paths) {

        const value = getNested(object, path);

        if (value !== undefined && value !== null) {
            return value;
        }

    }

    return null;
}


function fmt(value, digits = 4) {

    if (
        value === null ||
        value === undefined ||
        value === '' ||
        typeof value === 'object'
    ) {
        return 'Not available';
    }

    const number = Number(value);

    return Number.isFinite(number)
        ? number.toFixed(digits)
        : String(value);
}


function pFmt(value) {

    if (value === null || value === undefined) {
        return 'Not available';
    }

    const number = Number(value);

    return Number.isFinite(number)
        ? (
            number < 0.0001
                ? number.toExponential(2)
                : number.toFixed(5)
        )
        : String(value);
}


function metric(label, value, sub = '') {

    return `
        <div class="metric">
            <span class="label">${escapeHtml(label)}</span>
            <span class="value">${escapeHtml(value)}</span>
            <div class="sub">${escapeHtml(sub)}</div>
        </div>
    `;
}


function addRow(label, value, interpretation = '—') {

    return `
        <tr>
            <td>${escapeHtml(label)}</td>
            <td>${escapeHtml(value)}</td>
            <td>${escapeHtml(interpretation)}</td>
        </tr>
    `;
}


function renderStatistics(analysis, unit) {

    const direction = firstValue(analysis, [
        'interpretation.direction',
        'direction',
        'mann_kendall.trend',
        'mann_kendall.trend_direction'
    ]) ?? 'Not available';

    const slope = firstValue(analysis, [
        'linear_regression.slope_per_year',
        'linear_regression.slope',
        'slope_per_year'
    ]);

    const hac = firstValue(analysis, [
        'linear_regression.hac_p_value',
        'hac_p_value'
    ]);

    const ordinary = firstValue(analysis, [
        'linear_regression.p_value',
        'p_value'
    ]);

    const mkp = firstValue(analysis, [
        'mann_kendall.p_value',
        'mann_kendall.p'
    ]);

    const r2 = firstValue(analysis, [
        'linear_regression.r_squared',
        'linear_regression.r2',
        'r_squared'
    ]);

    const ci = firstValue(analysis, [
        'linear_regression.confidence_interval',
        'confidence_interval'
    ]);

    const hacci = firstValue(analysis, [
        'linear_regression.hac_confidence_interval'
    ]);

    const autocorr = firstValue(analysis, [
        'autocorrelation.lag_1_correlation',
        'autocorrelation.lag1_correlation'
    ]);

    const seasonal = firstValue(analysis, [
        'seasonal_mann_kendall.trend',
        'seasonal_mann_kendall.trend_direction'
    ]);

    const seasonalP = firstValue(analysis, [
        'seasonal_mann_kendall.p_value'
    ]);

    const slopeText = slope === null
        ? 'Not available'
        : `${fmt(slope, 5)} ${unit}/year`;

    document.getElementById('keyMetrics').innerHTML =

        metric('Trend Direction', String(direction)) +

        metric(
            'Annual Rate of Change',
            slopeText,
            'Linear regression slope'
        ) +

        metric(
            'Mann-Kendall p-value',
            pFmt(mkp),
            'Non-parametric trend test'
        ) +

        metric(
            'HAC-adjusted p-value',
            pFmt(hac),
            'Accounts for autocorrelation'
        ) +

        metric(
            'R-squared',
            fmt(r2, 4),
            'Linear model fit'
        ) +

        metric(
            'Observations',
            String(
                analysis.observation_count ?? 'Not available'
            )
        );


    let significance = 'Not available';

    if (hac !== null) {

        significance = Number(hac) < 0.05
            ? 'Significant at 5% (HAC-adjusted)'
            : 'Not statistically significant at 5% (HAC-adjusted)';
    }


    const ciText = Array.isArray(ci)
        ? ci.map(value => fmt(value, 5)).join(' to ')
        : 'Not available';

    const hacCiText = Array.isArray(hacci)
        ? hacci.map(value => fmt(value, 5)).join(' to ')
        : 'Not available';


    let rows = '';

    rows += addRow('Trend direction', direction);

    rows += addRow(
        'Linear slope per year',
        slopeText
    );

    rows += addRow(
        'Ordinary regression p-value',
        pFmt(ordinary)
    );

    rows += addRow(
        'HAC-adjusted p-value',
        pFmt(hac),
        significance
    );

    rows += addRow(
        'R-squared',
        fmt(r2, 5)
    );

    rows += addRow(
        'Linear confidence interval',
        ciText
    );

    // Correct variable name: hacCiText.
    rows += addRow(
        'HAC confidence interval',
        hacCiText
    );

    rows += addRow(
        'Mann-Kendall trend',
        String(
            firstValue(analysis, [
                'mann_kendall.trend',
                'mann_kendall.trend_direction'
            ]) ?? 'Not available'
        )
    );

    rows += addRow(
        'Mann-Kendall p-value',
        pFmt(mkp)
    );

    rows += addRow(
        'Seasonal Mann-Kendall trend',
        String(seasonal ?? 'Not available')
    );

    rows += addRow(
        'Seasonal Mann-Kendall p-value',
        pFmt(seasonalP)
    );

    rows += addRow(
        'Lag-1 residual autocorrelation',
        fmt(autocorr, 4)
    );

    document.getElementById('statisticsTable').innerHTML = rows;


    const cautions = [];

    if (
        autocorr !== null &&
        Math.abs(Number(autocorr)) >= 0.5
    ) {

        cautions.push(
            'Strong lag-1 residual autocorrelation was detected. ' +
            'Prefer HAC-adjusted inference and interpret ordinary ' +
            'regression p-values cautiously.'
        );
    }

    if (
        hac !== null &&
        ordinary !== null &&
        (
            (Number(hac) < 0.05) !==
            (Number(ordinary) < 0.05)
        )
    ) {

        cautions.push(
            'Ordinary and HAC-adjusted regression significance differ. ' +
            'The autocorrelation-adjusted result should be highlighted.'
        );
    }

    cautions.push(
        'A trend association does not establish causation. ' +
        'Statistical significance and trend magnitude are different concepts.'
    );

    document.getElementById(
        'scientificCaution'
    ).textContent = cautions.join(' ');
}


function renderAi(ai) {

    const explanation =
        ai.explanation ||
        ai.message ||
        'AI explanation is currently unavailable.';

    document.getElementById('aiOutput').textContent =
        explanation;

    document.getElementById('aiStatus').textContent =
        ai.success
            ? 'Gemini explanation received. Statistical values above remain calculated by Python.'
            : 'Gemini is temporarily unavailable or timed out. Scientific analysis remains independently available.';
}


// ------------------------------------------------------------------
// Main analysis submission
// ------------------------------------------------------------------

form.addEventListener('submit', async event => {

    event.preventDefault();

    if (!selectedLocation) {

        statusBox.textContent =
            'Please search for a location and select one of the suggestions.';

        statusBox.className = 'status error';

        searchInput.focus();

        return;
    }

    if (analysisController) {
        analysisController.abort();
    }

    analysisController = new AbortController();

    const timeout = setTimeout(
        () => analysisController.abort(),
        120000
    );

    button.disabled = true;

    button.innerHTML =
        '<span class="spinner"></span>Processing…';

    statusBox.className = 'status';

    statusBox.textContent =
        'Step 1/4: Requesting NASA observations...';

    document.getElementById('resultSection').style.display =
        'none';


    try {

        const payload = Object.fromEntries(
            new FormData(form).entries()
        );

        const response = await fetch(
            '/api/analyze',
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload),
                signal: analysisController.signal
            }
        );

        const result = await response.json();

        if (!response.ok || !result.success) {

            throw new Error(
                result.error || 'Analysis could not be completed.'
            );
        }


        // Dataset information.
        document.getElementById('sourceLabel').textContent =
            result.source_label;

        const info = [
            ['Variable', result.variable_name],
            ['Location', result.region],
            ['Observations', result.observation_count],
            ['Frequency', result.frequency],
            ['Unit', result.unit],
            [
                'Date range',
                result.start_date + ' to ' + result.end_date
            ],
            ['Data classification', result.data_type],
            ['Processing time', result.processing_seconds + ' seconds'],
            ['Spatial representation', 'Point observation']
        ];

        document.getElementById('datasetInfo').innerHTML =
            info.map(([key, value]) => `
                <div class="info-card">
                    <span>${escapeHtml(key)}</span>
                    <strong>${escapeHtml(value)}</strong>
                </div>
            `).join('');


        // Scientific source disclosure.
        const warning = document.getElementById('dataWarning');

        if (result.data_type === 'sample_demo') {

            warning.className = 'warning-box';

            warning.textContent =
                'DEMO DATA: These are synthetic observations, not NASA measurements. Do not use them as scientific evidence.';

        } else if (result.data_type === 'cached_nasa') {

            warning.className = 'warning-box';

            warning.textContent =
                'Cached NASA observations are being used. These are real NASA measurements retrieved previously.';

        } else {

            warning.className = 'warning-box';

            warning.textContent =
                'Live NASA observations were successfully retrieved. This is a point-based observation, not a country-wide or regional spatial average.';
        }


        // Chart.
        document.getElementById('chartFrame').src =
            result.chart.url + '?v=' + Date.now();


        // Statistics.
        renderStatistics(
            result.analysis || {},
            result.unit || ''
        );


        // Gemini.
        renderAi(
            result.ai_explanation || {}
        );


        // Report.
        const report = result.report || {};

        document.getElementById('reportStatus').textContent =
            report.success
                ? 'Scientific HTML report generated successfully.'
                : (
                    report.message ||
                    'Report generation needs attention.'
                );

        const link = document.getElementById('reportLink');

        if (report.url) {

            link.href = report.url;
            link.style.display = 'inline-block';

        } else {

            link.removeAttribute('href');
            link.style.display = 'none';
        }


        document.getElementById('resultSection').style.display =
            'block';

        statusBox.className = 'status success';

        statusBox.textContent =
            `Analysis completed successfully in ${result.processing_seconds} seconds.`;

    } catch (error) {

        statusBox.className = 'status error';

        statusBox.textContent =
            error.name === 'AbortError'
                ? 'The request timed out after 2 minutes. Try a shorter date range or try again later.'
                : 'Error: ' + error.message;

    } finally {

        clearTimeout(timeout);

        button.disabled = false;

        button.textContent =
            'Analyze Earth Science Trends';

        analysisController = null;
    }

});