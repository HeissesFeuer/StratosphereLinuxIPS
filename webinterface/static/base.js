const headers = {
    headers: {'Content-Type': 'application/json'}
}

fetch("/info", {
        method: "GET",
        headers: headers
        }).then(response => response.json())
        .then(data => {
                        document.getElementById("fileName").textContent=data['name'];
                        document.getElementById("fileSize").textContent=data['size_in_MB'];
                        document.getElementById("analysisStart").textContent=data['analysis_start'];
                        document.getElementById("analysisEnd").textContent=data['analysis_end'];
                    });