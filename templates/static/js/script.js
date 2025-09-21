async function doSearch(e) {
  e.preventDefault();
  const query = document.getElementById("search").value.trim();
  if (!query) return;

  const resultsDiv = document.getElementById("results");
  resultsDiv.innerHTML = "<p style='text-align:center;'>Loading...</p>";

  // helper: truncate text
  function truncateText(text, limit = 60) {
    if (!text) return "";
    return text.length > limit ? text.substring(0, limit) + "..." : text;
  }

  try {
    // 🔎 Fetch search results
    const res = await fetch(`/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error("Search request failed");
    const data = await res.json();

    resultsDiv.innerHTML = "";

    if (data.results && data.results.length > 0) {
      data.results.forEach((item, index) => {
        const div = document.createElement("div");
        div.className = "result-item";
        div.id = `result-${index}`;

        // short view
        const shortHTML = `
          <h3>${truncateText(item.English) || "Unknown"}</h3>
          <p><strong>isiZulu:</strong> ${item.isiZulu || "-"}</p>
          <p><strong>English:</strong> ${truncateText(item.English)}</p>
          <p><strong>isiXhosa:</strong> ${truncateText(item.isiXhosa)}</p>
          <p><strong>siSwati:</strong> ${truncateText(item.siSwati)}</p>
          <button class="toggle-btn" data-index="${index}">Show More</button>
          <div class="extra-info" id="extra-${index}"></div>
        `;

        // full view (hidden)
        const fullHTML = `
          <div class="full-view" id="full-${index}" style="display:none; margin-top:8px;">
            <p><strong>isiZulu:</strong> ${item.isiZulu || "-"}</p>
            <p><strong>English:</strong> ${item.English || "-"}</p>
            <p><strong>isiXhosa:</strong> ${item.isiXhosa || "-"}</p>
            <p><strong>siSwati:</strong> ${item.siSwati || "-"}</p>
            <p><strong>Context:</strong> ${item.Context || "-"}</p>
            <p><strong>Page:</strong> ${item.Page || "-"}</p>
            ${item.file_path ? `<p><a href="${item.file_path}" target="_blank">📂 View File</a></p>` : ""}
            <button class="toggle-btn" data-index="${index}">Show Less</button>
          </div>
        `;

        div.innerHTML = shortHTML + fullHTML;
        resultsDiv.appendChild(div);

        // attach toggle button
        div.querySelectorAll(".toggle-btn").forEach(btn => {
          btn.addEventListener("click", () => {
            const idx = btn.dataset.index;
            const fullDiv = document.getElementById(`full-${idx}`);
            if (fullDiv.style.display === "none") {
              fullDiv.style.display = "block";
              btn.style.display = "none"; // hide "Show More"
            } else {
              fullDiv.style.display = "none";
              // re-show the "Show More" button
              div.querySelector(`.toggle-btn[data-index="${idx}"]`).style.display = "inline-block";
            }
          });
        });

        // ✅ Fetch frequency for the current isiZulu word
        fetch(`/frequency?q=${encodeURIComponent(item.isiZulu)}`)
          .then(r => r.json())
          .then(freqData => {
            const extra = document.getElementById(`extra-${index}`);
            if (freqData && freqData.frequency !== undefined) {
              extra.innerHTML += `<p><strong>Frequency:</strong> ${freqData.frequency}</p>`;
            } else {
              extra.innerHTML += `<p><strong>Frequency:</strong> 0 (None found)</p>`;
            }
          })
          .catch(() => {
            const extra = document.getElementById(`extra-${index}`);
            extra.innerHTML += `<p style="color:red;"><strong>Error loading frequency</strong></p>`;
          });

        // ✅ Fetch common word pairs for the current isiZulu word
        fetch(`/pairs?q=${encodeURIComponent(item.isiZulu)}`)
          .then(r => r.json())
          .then(pairData => {
            const extra = document.getElementById(`extra-${index}`);
            if (pairData.common_pairs && pairData.common_pairs.length > 0) {
              extra.innerHTML += `<p><strong>Common pairs:</strong></p><ul>`;
              pairData.common_pairs.forEach(p => {
                extra.innerHTML += `<li>${p.pair} (${p.count})</li>`;
              });
              extra.innerHTML += `</ul>`;
            } else {
              extra.innerHTML += `<p><strong>Common pairs:</strong> None found</p>`;
            }
          })
          .catch(() => {
            const extra = document.getElementById(`extra-${index}`);
            extra.innerHTML += `<p style="color:red;"><strong>Error loading pairs</strong></p>`;
          });
      });
    } else if (data.did_you_mean && data.did_you_mean.length > 0) {
      resultsDiv.innerHTML = `<p>No exact results found. Did you mean: <strong>${data.did_you_mean.join(", ")}</strong>?</p>`;
    } else {
      resultsDiv.innerHTML = "<p style='text-align:center; color:#555;'>No results found.</p>";
    }
  } catch (err) {
    resultsDiv.innerHTML = "<p style='color:red; text-align:center;'>Error fetching results.</p>";
    console.error(err);
  }
}

// Attach function to the form
document.querySelector(".search-box").addEventListener("submit", doSearch);
