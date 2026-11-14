(() => {
    "use strict";

    const byId = (id) => document.getElementById(id);
    const form = byId("analysisForm");
    const button = byId("analyzeButton");
    const statusBox = byId("status");
    const searchInput = byId("locationSearch");
    const suggestions = byId("suggestions");

    let selectedLocation = null;
    let geocodeTimer = null;
    let geocodeController = null;
    let analysisController = null;
    let activeSuggestionIndex = -1;
    let currentSuggestions = [];
    let globe = null;
    let resizeObserver = null;

    const VARIABLE_LABELS = {
        temperature: "Air Temperature",
        humidity: "Relative Humidity",
        precipitation: "Precipitation",
        wind_speed: "Wind Speed",
        solar_radiation: "Solar Radiation"
    };

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (character) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        }[character]));
    }

    function setStatus(message, type = "") {
        statusBox.textContent = message;
        statusBox.className = `status${type ? ` ${type}` : ""}`;
    }

    function updateCoordinateDisplay(latitude, longitude) {
        byId("latitudeDisplay").textContent = Number(latitude).toFixed(4) + "°";
        byId("longitudeDisplay").textContent = Number(longitude).toFixed(4) + "°";
        byId("globeCoordinates").textContent =
            `LAT ${Number(latitude).toFixed(4)}°  /  LON ${Number(longitude).toFixed(4)}°`;
    }

    function hideSuggestions() {
        suggestions.style.display = "none";
        activeSuggestionIndex = -1;
    }

    function showSuggestionMessage(message) {
        suggestions.innerHTML = `<div class="suggestion-message">${escapeHtml(message)}</div>`;
        suggestions.style.display = "block";
    }

    function updateGlobeMarker() {
        if (!globe) return;
        const points = selectedLocation ? [{
            lat: Number(selectedLocation.latitude),
            lng: Number(selectedLocation.longitude),
            size: 0.48,
            label: selectedLocation.short_name
        }] : [];
        globe.pointsData(points);
        if (selectedLocation) {
            globe.pointOfView({
                lat: Number(selectedLocation.latitude),
                lng: Number(selectedLocation.longitude),
                altitude: 1.75
            }, 1100);
        }
    }

    function commitLocation(place, source = "search") {
        const latitude = Number(place.latitude);
        const longitude = Number(place.longitude);

        if (!Number.isFinite(latitude) || !Number.isFinite(longitude) ||
            latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
            setStatus("The selected location has invalid coordinates. Please select it again.", "error");
            return;
        }

        selectedLocation = {
            name: place.name || place.short_name || "Selected location",
            short_name: place.short_name || place.name || "Selected location",
            latitude,
            longitude
        };

        searchInput.value = selectedLocation.short_name;
        byId("region").value = selectedLocation.short_name;
        byId("latitude").value = String(latitude);
        byId("longitude").value = String(longitude);
        byId("locationHint").textContent = source === "globe"
            ? "Coordinates selected from the globe. This point can now be analyzed."
            : "Location selected. Coordinates detected automatically.";

        byId("selectedLocationName").textContent = selectedLocation.short_name;
        updateCoordinateDisplay(latitude, longitude);
        updateGlobeMarker();
        hideSuggestions();
        setStatus("Location selected. Choose a variable and run the analysis.", "success");
    }

    function clearLocation() {
        selectedLocation = null;
        searchInput.value = "";
        byId("region").value = "";
        byId("latitude").value = "";
        byId("longitude").value = "";
        byId("latitudeDisplay").textContent = "—";
        byId("longitudeDisplay").textContent = "—";
        byId("globeCoordinates").textContent = "AWAITING LOCATION SELECTION";
        byId("selectedLocationName").textContent = "No location selected";
        byId("locationHint").textContent = "Search and select a place, or click directly on the globe.";
        updateGlobeMarker();
        hideSuggestions();
        setStatus("Select a location to begin exploring Earth observations.");
    }

    function renderLocationSuggestions(results) {
        currentSuggestions = results;
        activeSuggestionIndex = -1;

        if (!results.length) {
            showSuggestionMessage("No matching locations found. Try another spelling.");
            return;
        }

        suggestions.innerHTML = results.map((place, index) => {
            const details = [place.city, place.state, place.country].filter(Boolean).join(", ");
            return `
                <button type="button" class="suggestion" role="option" data-index="${index}">
                    <strong>${escapeHtml(place.name)}</strong>
                    <small>${escapeHtml(details || place.short_name || "")}</small>
                </button>`;
        }).join("");

        suggestions.querySelectorAll(".suggestion[data-index]").forEach((element) => {
            element.addEventListener("click", () => {
                commitLocation(currentSuggestions[Number(element.dataset.index)], "search");
            });
        });
        suggestions.style.display = "block";
    }

    async function searchLocations(query) {
        if (query.length < 2) {
            hideSuggestions();
            return;
        }

        if (geocodeController) geocodeController.abort();
        geocodeController = new AbortController();
        const controller = geocodeController;

        showSuggestionMessage("Searching global locations…");

        try {
            const response = await fetch("/api/geocode?q=" + encodeURIComponent(query), {
                signal: controller.signal
            });
            const data = await response.json();

            if (controller !== geocodeController) return;
            if (!response.ok || !data.success) {
                throw new Error(data.error || "Location search failed.");
            }
            renderLocationSuggestions(data.results || []);
        } catch (error) {
            if (error.name === "AbortError") return;
            showSuggestionMessage(error.message || "Location search is temporarily unavailable.");
        }
    }

    function selectGlobeCoordinates(latitude, longitude) {
        latitude = Number(Number(latitude).toFixed(5));
        longitude = Number(Number(longitude).toFixed(5));

        const label = `Coordinates ${latitude.toFixed(4)}°, ${longitude.toFixed(4)}°`;

        commitLocation({
            name: label,
            short_name: label,
            latitude,
            longitude
        }, "globe");
    }
    function loadCountryLayers() {
        // Show Pakistan immediately, even if the country dataset is unavailable.
        const pakistanLabel = {
            lat: 30.3753,
            lng: 69.3451,
            text: "PAKISTAN",
            isPakistan: true
        };

        globe.labelsData([pakistanLabel])
            .labelLat("lat")
            .labelLng("lng")
            .labelText("text")
            .labelColor(d => d.isPakistan ? "#ffe08a" : "#ffffff")
            .labelSize(d => d.isPakistan ? 2.2 : 1.35)
            .labelAltitude(0.025)
            .labelDotRadius(d => d.isPakistan ? 0.12 : 0.035)
            .onLabelClick((label, event, coords) => selectGlobeCoordinates(coords.lat, coords.lng));

        const datasetUrl =
            "https://raw.githubusercontent.com/vasturiano/globe.gl/master/example/datasets/ne_110m_admin_0_countries.geojson";

        function getCountryCenter(feature) {
            const geometry = feature.geometry;
            if (!geometry) return null;

            const polygons = geometry.type === "Polygon"
                ? [geometry.coordinates]
                : geometry.type === "MultiPolygon"
                    ? geometry.coordinates
                    : [];

            let largestRing = null;

            polygons.forEach(polygon => {
                const ring = polygon && polygon[0];
                if (ring && (!largestRing || ring.length > largestRing.length)) {
                    largestRing = ring;
                }
            });

            if (!largestRing || largestRing.length < 3) return null;

            let x = 0, y = 0, z = 0;

            largestRing.forEach(([longitude, latitude]) => {
                const lat = latitude * Math.PI / 180;
                const lng = longitude * Math.PI / 180;

                x += Math.cos(lat) * Math.cos(lng);
                y += Math.cos(lat) * Math.sin(lng);
                z += Math.sin(lat);
            });

            const lng = Math.atan2(y, x) * 180 / Math.PI;
            const hyp = Math.sqrt(x * x + y * y);
            const lat = Math.atan2(z, hyp) * 180 / Math.PI;

            return { lat, lng };
        }

        fetch(datasetUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error("Country dataset HTTP " + response.status);
                }
                return response.json();
            })
            .then(data => {
                const features = (data.features || []).filter(feature =>
                    feature.geometry &&
                    ["Polygon", "MultiPolygon"].includes(feature.geometry.type)
                );

                if (!features.length) {
                    throw new Error("Country dataset contains no valid country boundaries.");
                }

                globe
                    .polygonsData(features)
                    .polygonLabel(feature =>
                        feature.properties.ADMIN ||
                        feature.properties.NAME ||
                        "Country"
                    )
                    .polygonCapColor(() => "rgba(60, 145, 170, 0.10)")
                    .polygonSideColor(() => "rgba(30, 90, 120, 0.12)")
                    .polygonStrokeColor(() => "rgba(170, 220, 230, 0.65)")
                    .polygonAltitude(0.0018)
                    .polygonsTransitionDuration(500)
                    .onPolygonClick((feature, event, coords) => selectGlobeCoordinates(coords.lat, coords.lng));

                const labels = [];
                let pakistanFound = false;

                features.forEach(feature => {
                    const properties = feature.properties || {};
                    const name = properties.ADMIN || properties.NAME;

                    if (!name) return;

                    const center = getCountryCenter(feature);
                    if (!center) return;

                    const isPakistan = name.toLowerCase() === "pakistan";

                    if (isPakistan) pakistanFound = true;

                    labels.push({
                        lat: isPakistan ? 30.3753 : center.lat,
                        lng: isPakistan ? 69.3451 : center.lng,
                        text: isPakistan ? "PAKISTAN" : name,
                        isPakistan
                    });
                });

                if (!pakistanFound) {
                    labels.push(pakistanLabel);
                }

                // Keep a curated set of major country labels permanently visible.
                // All other country names remain available through polygon hover.
                const permanentCountryNames = new Set([
                    "pakistan",
                    "india",
                    "china",
                    "afghanistan",
                    "iran",
                    "saudi arabia",
                    "united arab emirates",
                    "turkey",
                    "russia",
                    "united states of america",
                    "canada",
                    "brazil",
                    "australia",
                    "japan",
                    "indonesia",
                    "united kingdom",
                    "france",
                    "germany",
                    "egypt"
                ]);

                globe.labelsData(
                    labels.filter(label =>
                        permanentCountryNames.has(label.text.toLowerCase())
                    )
                );

                console.info(
                    "TrendMatrix AI: Country boundaries loaded:",
                    features.length,
                    "| Country labels:",
                    labels.length
                );
            })
            .catch(error => {
                console.error("TrendMatrix AI country layer error:", error);
                console.warn("Pakistan label remains visible; country boundaries could not be loaded.");
            });
    }
    function initializeGlobe() {
        const container = byId("earthGlobe");
        const loading = byId("globeLoading");

        if (typeof window.Globe !== "function") {
            loading.innerHTML = "<span>3D globe library could not be loaded. Check your internet connection and refresh.</span>";
            return;
        }

        try {
            globe = window.Globe()(container)
                .globeImageUrl("https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
                .bumpImageUrl("https://unpkg.com/three-globe/example/img/earth-topology.png")
                .backgroundColor("rgba(0,0,0,0)")
                .showAtmosphere(true)
                .atmosphereColor("#4da9c7")
                .atmosphereAltitude(0.16)
                .showGraticules(true)

                .pointsData([])
                .pointLat("lat")
                .pointLng("lng")
                .pointColor(() => "#75f0d5")
                .pointRadius("size")
                .pointAltitude(0.018)
                .pointResolution(18)
                .pointLabel("label")
                .onGlobeClick(({ lat, lng }) => selectGlobeCoordinates(lat, lng));

            globe.width(container.clientWidth).height(container.clientHeight);
            loadCountryLayers();
            globe.pointOfView({ lat: 30.3753, lng: 69.3451, altitude: 2.25 }, 0);
            const controls = globe.controls();
            controls.autoRotate = false;
            controls.autoRotateSpeed = 0.32;
            controls.enableDamping = true;
            controls.dampingFactor = 0.08;
            controls.minDistance = 115;
            controls.maxDistance = 520;

            byId("globeZoomIn").addEventListener("click", () => {
                const view = globe.pointOfView();
                globe.pointOfView({ ...view, altitude: Math.max(0.75, view.altitude * 0.78) }, 350);
            });
            byId("globeZoomOut").addEventListener("click", () => {
                const view = globe.pointOfView();
                globe.pointOfView({ ...view, altitude: Math.min(4.5, view.altitude * 1.25) }, 350);
            });
            byId("globeReset").addEventListener("click", () => {
                globe.pointOfView({ lat: 30.3753, lng: 69.3451, altitude: 2.25 }, 700);
                controls.autoRotate = false;
            });

            resizeObserver = new ResizeObserver(() => {
                if (!globe) return;
                globe.width(container.clientWidth);
                globe.height(container.clientHeight);
            });
            resizeObserver.observe(container);

            setTimeout(() => loading.classList.add("hidden"), 900);
        } catch (error) {
            loading.innerHTML = `<span>Globe initialization failed: ${escapeHtml(error.message)}</span>`;
        }
    }

    function getNested(object, path) {
        return path.split(".").reduce((value, key) =>
            value && value[key] !== undefined ? value[key] : undefined, object);
    }

    function firstValue(object, paths) {
        for (const path of paths) {
            const value = getNested(object, path);
            if (value !== undefined && value !== null) return value;
        }
        return null;
    }

    function fmt(value, digits = 4) {
        if (value === null || value === undefined || value === "" || typeof value === "object") {
            return "Not available";
        }
        const number = Number(value);
        return Number.isFinite(number) ? number.toFixed(digits) : String(value);
    }

    function pFmt(value) {
        if (value === null || value === undefined) return "Not available";
        const number = Number(value);
        return Number.isFinite(number)
            ? (number < 0.0001 ? number.toExponential(2) : number.toFixed(5))
            : String(value);
    }

    function metric(label, value, sub = "") {
        return `<div class="metric">
            <span class="label">${escapeHtml(label)}</span>
            <span class="value">${escapeHtml(value)}</span>
            <div class="sub">${escapeHtml(sub)}</div>
        </div>`;
    }

    function addRow(label, value, interpretation = "—") {
        return `<tr><td>${escapeHtml(label)}</td><td>${escapeHtml(value)}</td><td>${escapeHtml(interpretation)}</td></tr>`;
    }

    function renderStatistics(analysis, unit) {
        const direction = firstValue(analysis, [
            "interpretation.direction", "direction", "mann_kendall.trend", "mann_kendall.trend_direction"
        ]) ?? "Not available";
        const slope = firstValue(analysis, [
            "linear_regression.slope_per_year", "linear_regression.slope", "slope_per_year"
        ]);
        const hac = firstValue(analysis, ["linear_regression.hac_p_value", "hac_p_value"]);
        const ordinary = firstValue(analysis, ["linear_regression.p_value", "p_value"]);
        const mkp = firstValue(analysis, ["mann_kendall.p_value", "mann_kendall.p"]);
        const r2 = firstValue(analysis, ["linear_regression.r_squared", "linear_regression.r2", "r_squared"]);
        const ci = firstValue(analysis, ["linear_regression.confidence_interval", "confidence_interval"]);
        const hacci = firstValue(analysis, ["linear_regression.hac_confidence_interval"]);
        const autocorr = firstValue(analysis, [
            "autocorrelation.lag_1_correlation", "autocorrelation.lag1_correlation"
        ]);
        const seasonal = firstValue(analysis, [
            "seasonal_mann_kendall.trend", "seasonal_mann_kendall.trend_direction"
        ]);
        const seasonalP = firstValue(analysis, ["seasonal_mann_kendall.p_value"]);
        const slopeText = slope === null ? "Not available" : `${fmt(slope, 5)} ${unit}/year`;

        byId("keyMetrics").innerHTML =
            metric("Trend direction", String(direction)) +
            metric("Annual rate of change", slopeText, "Linear regression slope") +
            metric("Mann-Kendall p-value", pFmt(mkp), "Non-parametric trend test") +
            metric("HAC-adjusted p-value", pFmt(hac), "Autocorrelation-adjusted inference") +
            metric("R-squared", fmt(r2, 4), "Linear model fit") +
            metric("Observations", String(analysis.observation_count ?? "Not available"));

        const significance = hac === null ? "Not available" :
            (Number(hac) < 0.05 ? "Significant at 5% (HAC-adjusted)" :
                "Not statistically significant at 5% (HAC-adjusted)");
        const ciText = Array.isArray(ci) ? ci.map(value => fmt(value, 5)).join(" to ") : "Not available";
        const hacCiText = Array.isArray(hacci) ? hacci.map(value => fmt(value, 5)).join(" to ") : "Not available";

        let rows = "";
        rows += addRow("Trend direction", direction);
        rows += addRow("Linear slope per year", slopeText);
        rows += addRow("Ordinary regression p-value", pFmt(ordinary));
        rows += addRow("HAC-adjusted p-value", pFmt(hac), significance);
        rows += addRow("R-squared", fmt(r2, 5));
        rows += addRow("Linear confidence interval", ciText);
        rows += addRow("HAC confidence interval", hacCiText);
        rows += addRow("Mann-Kendall trend", String(firstValue(analysis, [
            "mann_kendall.trend", "mann_kendall.trend_direction"
        ]) ?? "Not available"));
        rows += addRow("Mann-Kendall p-value", pFmt(mkp));
        rows += addRow("Seasonal Mann-Kendall trend", String(seasonal ?? "Not available"));
        rows += addRow("Seasonal Mann-Kendall p-value", pFmt(seasonalP));
        rows += addRow("Lag-1 residual autocorrelation", fmt(autocorr, 4));
        byId("statisticsTable").innerHTML = rows;

        const cautions = [];
        if (autocorr !== null && Math.abs(Number(autocorr)) >= 0.5) {
            cautions.push("Strong lag-1 residual autocorrelation was detected. Prefer HAC-adjusted inference and interpret ordinary regression p-values cautiously.");
        }
        if (hac !== null && ordinary !== null &&
            ((Number(hac) < 0.05) !== (Number(ordinary) < 0.05))) {
            cautions.push("Ordinary and HAC-adjusted regression significance differ. Highlight the autocorrelation-adjusted result.");
        }
        cautions.push("A trend association does not establish causation. Statistical significance and trend magnitude are different concepts.");
        byId("scientificCaution").textContent = cautions.join(" ");
    }

    function renderAi(ai) {
        byId("aiOutput").textContent = ai.explanation || ai.message ||
            "AI explanation is currently unavailable.";
        byId("aiStatus").textContent = ai.success
            ? "Gemini explanation received. Statistical values above remain calculated by Python."
            : "Gemini is temporarily unavailable or timed out. Scientific analysis remains independently available.";
    }

    function renderAnalysisResult(result) {
        byId("sourceLabel").textContent = result.source_label || "Source not specified";
        const info = [
            ["Variable", result.variable_name],
            ["Location", result.region],
            ["Observations", result.observation_count],
            ["Frequency", result.frequency],
            ["Unit", result.unit],
            ["Date range", `${result.start_date} to ${result.end_date}`],
            ["Data classification", result.data_type],
            ["Spatial representation", "Point observation"]
        ];
        byId("datasetInfo").innerHTML = info.map(([key, value]) => `
            <div class="info-card"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>
        `).join("");

        const warning = byId("dataWarning");
        warning.className = "warning-box";
        if (result.data_type === "sample_demo") {
            warning.textContent = "DEMO DATA: These are synthetic observations, not NASA measurements. Do not use them as scientific evidence.";
        } else if (result.data_type === "cached_nasa") {
            warning.textContent = "Cached NASA observations are being used. These are real NASA measurements retrieved previously.";
        } else {
            warning.textContent = "Live NASA observations were successfully retrieved. This is a point-based observation, not a country-wide or regional spatial average.";
        }

        if (result.chart && result.chart.url) {
            byId("chartFrame").src = result.chart.url + "?v=" + Date.now();
        }
        renderStatistics(result.analysis || {}, result.unit || "");
        renderAi(result.ai_explanation || {});

        const report = result.report || {};
        byId("reportStatus").textContent = report.success
            ? "Scientific HTML report generated successfully."
            : (report.message || "Report generation needs attention.");
        const link = byId("reportLink");
        if (report.url) {
            link.href = report.url;
            link.style.display = "inline-flex";
        } else {
            link.removeAttribute("href");
            link.style.display = "none";
        }

        byId("resultSection").style.display = "block";
        byId("resultSection").scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function submitAnalysis(event) {
        event.preventDefault();

        if (!selectedLocation) {
            setStatus("Please search for and select a location, or click on the globe first.", "error");
            searchInput.focus();
            return;
        }

        const start = byId("start_date").value;
        const end = byId("end_date").value;
        if (!start || !end || start >= end) {
            setStatus("Please select a valid date range. The end date must be later than the start date.", "error");
            return;
        }

        if (analysisController) analysisController.abort();
        analysisController = new AbortController();
        const controller = analysisController;
        const timeout = setTimeout(() => controller.abort(), 120000);

        button.disabled = true;
        button.innerHTML = '<span><i class="spinner"></i>Processing NASA observations…</span><b>…</b>';
        setStatus("Requesting NASA observations, processing the time series, and preparing scientific results…");
        byId("resultSection").style.display = "none";

        try {
            const payload = Object.fromEntries(new FormData(form).entries());
            const response = await fetch("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
                signal: controller.signal
            });
            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.error || "Analysis could not be completed.");
            }

            renderAnalysisResult(result);
            setStatus(`Analysis completed successfully in ${result.processing_seconds ?? "—"} seconds.`, "success");
        } catch (error) {
            setStatus(error.name === "AbortError"
                ? "The request timed out after 2 minutes. Try a shorter date range or try again later."
                : "Analysis error: " + error.message, "error");
        } finally {
            clearTimeout(timeout);
            button.disabled = false;
            button.innerHTML = "<span>Run trend analysis</span><b aria-hidden=\"true\">→</b>";
            if (analysisController === controller) analysisController = null;
        }
    }

    function bindEvents() {
        searchInput.addEventListener("input", () => {
            selectedLocation = null;
            byId("region").value = "";
            byId("latitude").value = "";
            byId("longitude").value = "";
            byId("latitudeDisplay").textContent = "—";
            byId("longitudeDisplay").textContent = "—";
            byId("selectedLocationName").textContent = "No location selected";
            updateGlobeMarker();

            clearTimeout(geocodeTimer);
            if (geocodeController) geocodeController.abort();

            const query = searchInput.value.trim();
            if (query.length < 2) {
                hideSuggestions();
                return;
            }
            geocodeTimer = setTimeout(() => searchLocations(query), 400);
        });

        searchInput.addEventListener("keydown", (event) => {
            const items = suggestions.querySelectorAll(".suggestion[data-index]");
            if (event.key === "ArrowDown" && items.length) {
                event.preventDefault();
                activeSuggestionIndex = Math.min(activeSuggestionIndex + 1, items.length - 1);
            } else if (event.key === "ArrowUp" && items.length) {
                event.preventDefault();
                activeSuggestionIndex = Math.max(activeSuggestionIndex - 1, 0);
            } else if (event.key === "Enter" && items.length) {
                event.preventDefault();
                if (activeSuggestionIndex >= 0) {
                    commitLocation(currentSuggestions[activeSuggestionIndex], "search");
                }
                return;
            } else if (event.key === "Escape") {
                hideSuggestions();
                return;
            }
            items.forEach((item, index) => item.classList.toggle("active", index === activeSuggestionIndex));
        });

        byId("clearLocation").addEventListener("click", clearLocation);
        document.addEventListener("click", (event) => {
            if (!event.target.closest("#locationSearch") &&
                !event.target.closest("#suggestions")) hideSuggestions();
        });

        document.querySelectorAll(".layer-option").forEach((layerButton) => {
            layerButton.addEventListener("click", () => {
                const variable = layerButton.dataset.variable;
                byId("variable").value = variable;
                document.querySelectorAll(".layer-option").forEach((item) =>
                    item.classList.toggle("active", item === layerButton));
            });
        });

        byId("variable").addEventListener("change", () => {
            document.querySelectorAll(".layer-option").forEach((item) =>
                item.classList.toggle("active", item.dataset.variable === byId("variable").value));
        });

        form.addEventListener("submit", submitAnalysis);
    }

    document.addEventListener("DOMContentLoaded", () => {
        initializeGlobe();
        bindEvents();
    });
})();
