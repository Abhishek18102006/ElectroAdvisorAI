const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const htmlPath = path.resolve(__dirname, '..', 'docs', 'project_interview_defense_guide.html');
  const rootPdfPath = path.resolve(__dirname, '..', 'ElectroAdvisor_AI_Project_Explanation_Guide.pdf');
  const docsPdfPath = path.resolve(__dirname, '..', 'docs', 'ElectroAdvisor_AI_Project_Explanation_Guide.pdf');

  console.log('[PDF Generator] Launching headless Chromium...');
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  const fileUrl = 'file:///' + htmlPath.replace(/\\/g, '/');
  console.log(`[PDF Generator] Loading HTML: ${fileUrl}`);
  await page.goto(fileUrl, { waitUntil: 'networkidle' });

  console.log('[PDF Generator] Generating A4 PDF document...');
  const pdfBuffer = await page.pdf({
    format: 'A4',
    printBackground: true,
    margin: {
      top: '16mm',
      bottom: '16mm',
      left: '14mm',
      right: '14mm'
    }
  });

  fs.writeFileSync(rootPdfPath, pdfBuffer);
  fs.writeFileSync(docsPdfPath, pdfBuffer);

  await browser.close();

  console.log(`[PDF Generator] SUCCESS! Saved PDF to:`);
  console.log(` - ${rootPdfPath}`);
  console.log(` - ${docsPdfPath}`);
  console.log(` - File size: ${(pdfBuffer.length / 1024).toFixed(1)} KB`);
})().catch(err => {
  console.error('[PDF Generator] Error:', err);
  process.exit(1);
});
