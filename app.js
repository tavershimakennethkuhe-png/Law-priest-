const resultBox = document.getElementById("result");

async function loadSummary() {
  try {
    const response = await fetch("/api/summary");
    const data = await response.json();
    document.getElementById("total").textContent = data.total_cases;
    document.getElementById("outcome-count").textContent = Object.keys(data.outcomes).length;
    document.getElementById("area-count").textContent = Object.keys(data.areas).length;
  } catch (error) {
    document.getElementById("total").textContent = "Unavailable";
  }
}

async function loadCases() {
  const body = document.getElementById("cases-body");
  try {
    const response = await fetch("/api/cases");
    const cases = await response.json();
    body.innerHTML = "";
    if (!cases.length) {
      body.innerHTML = '<tr><td colspan="4">No case records found.</td></tr>';
      return;
    }
    for (const item of cases) {
      const row = document.createElement("tr");
      [item.case_name, item.area_of_law, item.outcome, item.sentence].forEach(value => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      body.appendChild(row);
    }
  } catch (error) {
    body.innerHTML = '<tr><td colspan="4">Could not load case records. Start the API server first.</td></tr>';
  }
}

document.getElementById("analyze-btn").addEventListener("click", async () => {
  const text = document.getElementById("legal-text").value;
  resultBox.textContent = "Analyzing…";
  try {
    const response = await fetch("/api/analyze", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text})
    });
    const data = await response.json();
    resultBox.textContent = `${data.summary}\nKeywords: ${data.keywords.join(", ") || "None found"}\n${data.disclaimer}`;
  } catch (error) {
    resultBox.textContent = "Could not connect to the backend. Follow the README setup steps.";
  }
});

document.getElementById("predict-btn").addEventListener("click", async () => {
  const text = document.getElementById("legal-text").value;
  resultBox.textContent = "Checking predefined indicators…";
  try {
    const response = await fetch("/api/predict", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text})
    });
    const data = await response.json();
    resultBox.textContent = `Demo result: ${data.outcome}\n${data.reason}\n${data.disclaimer || ""}`;
  } catch (error) {
    resultBox.textContent = "Could not connect to the backend. Follow the README setup steps.";
  }
});

loadSummary();
loadCases();
