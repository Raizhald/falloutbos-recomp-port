# Settings window for the Fallout: Brotherhood of Steel port.
# Reads and writes settings.ini in the project folder; Play.cmd applies it.
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$root = Split-Path -Parent $PSScriptRoot
$ini  = Join-Path $root 'settings.ini'

$cfg = [ordered]@{
    Renderer = 'GPU'; ResolutionScale = '2'; TextureFilter = '2'; VSync = '1'; Fullscreen = '0'
    WindowScale = '2'; FPSLimit = '60'; Mute = '0'
}
if (Test-Path $ini) {
    foreach ($line in Get-Content $ini) {
        if ($line -match '^\s*([A-Za-z]+)\s*=\s*(.*?)\s*$') { $cfg[$Matches[1]] = $Matches[2] }
    }
}

function Save-Settings {
    $lines = @(
        '; Fallout: Brotherhood of Steel - game settings. Change them with Settings.cmd.'
        '[Video]'
        "Renderer=$($cfg.Renderer)"
        "ResolutionScale=$($cfg.ResolutionScale)"
        "TextureFilter=$($cfg.TextureFilter)"
        "VSync=$($cfg.VSync)"
        "Fullscreen=$($cfg.Fullscreen)"
        "WindowScale=$($cfg.WindowScale)"
        "FPSLimit=$($cfg.FPSLimit)"
        '[Audio]'
        "Mute=$($cfg.Mute)"
    )
    Set-Content -Path $ini -Value $lines -Encoding ASCII
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Fallout: Brotherhood of Steel - Settings'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.StartPosition = 'CenterScreen'
$form.AutoSize = $true
$form.AutoSizeMode = 'GrowAndShrink'
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.Padding = New-Object System.Windows.Forms.Padding(12)

$grid = New-Object System.Windows.Forms.TableLayoutPanel
$grid.ColumnCount = 2
$grid.AutoSize = $true
$grid.Dock = 'Fill'
$form.Controls.Add($grid)

function Add-Row($label, $control) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $label
    $l.AutoSize = $true
    $l.Anchor = 'Left'
    $l.Margin = New-Object System.Windows.Forms.Padding(3, 8, 12, 3)
    $grid.Controls.Add($l)
    $control.Margin = New-Object System.Windows.Forms.Padding(3, 5, 3, 3)
    $grid.Controls.Add($control)
}

function New-Combo($items, $selected) {
    $c = New-Object System.Windows.Forms.ComboBox
    $c.DropDownStyle = 'DropDownList'
    $c.Width = 260
    foreach ($i in $items) { [void]$c.Items.Add($i) }
    $c.SelectedIndex = [Math]::Max(0, [Math]::Min($items.Count - 1, $selected))
    return $c
}

$renderer = New-Combo @('Graphics card (Direct3D 11)', 'Software (CPU, slower)') `
                      ($(if ($cfg.Renderer -ieq 'GPU') { 0 } else { 1 }))
Add-Row 'Renderer' $renderer

$res = New-Combo @('1x - 640 x 480 (original)', '2x - 1280 x 960', '3x - 1920 x 1440',
                   '4x - 2560 x 1920') ([int]$cfg.ResolutionScale - 1)
Add-Row 'Resolution' $res

$tex = New-Combo @('Original', 'Smooth (mipmaps)', 'Best (smooth + bicubic)') ([int]$cfg.TextureFilter)
Add-Row 'Texture filtering' $tex

$mode = New-Combo @('Window', 'Full screen') ([int]($cfg.Fullscreen -eq '1'))
Add-Row 'Display mode' $mode

$win = New-Combo @('1x - 640 x 480', '2x - 1280 x 960', '3x - 1920 x 1440') ([int]$cfg.WindowScale - 1)
Add-Row 'Window size' $win

$fpsValues = @('30', '60', '120', '0')
$fps = New-Combo @('30', '60 (recommended)', '120', 'Unlimited') ([Array]::IndexOf($fpsValues, $cfg.FPSLimit))
if ($fps.SelectedIndex -lt 0) { $fps.SelectedIndex = 1 }
Add-Row 'Frame rate limit' $fps

$vsync = New-Object System.Windows.Forms.CheckBox
$vsync.Text = 'V-Sync (no screen tearing)'
$vsync.AutoSize = $true
$vsync.Checked = ($cfg.VSync -ne '0')
Add-Row 'Sync' $vsync

$mute = New-Object System.Windows.Forms.CheckBox
$mute.Text = 'Mute sound'
$mute.AutoSize = $true
$mute.Checked = ($cfg.Mute -eq '1')
Add-Row 'Audio' $mute

$note = New-Object System.Windows.Forms.Label
$note.AutoSize = $true
$note.MaximumSize = New-Object System.Drawing.Size(420, 0)
$note.ForeColor = [System.Drawing.Color]::DimGray
$note.Margin = New-Object System.Windows.Forms.Padding(3, 12, 3, 6)
$note.Text = "Resolution, texture filtering and V-Sync need the graphics card renderer. " +
             "In game, F11 or Alt+Enter switches between window and full screen. " +
             "The window shrinks to fit the screen if it is too large."
$grid.Controls.Add($note)
$grid.SetColumnSpan($note, 2)

function Update-Enabled {
    $gpu = ($renderer.SelectedIndex -eq 0)
    $res.Enabled = $gpu
    $tex.Enabled = $gpu
    $vsync.Enabled = $gpu
}
$renderer.Add_SelectedIndexChanged({ Update-Enabled })
Update-Enabled

$buttons = New-Object System.Windows.Forms.FlowLayoutPanel
$buttons.FlowDirection = 'RightToLeft'
$buttons.AutoSize = $true
$buttons.Dock = 'Fill'
$grid.Controls.Add($buttons)
$grid.SetColumnSpan($buttons, 2)

function New-Button($text) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text
    $b.AutoSize = $true
    $b.Padding = New-Object System.Windows.Forms.Padding(8, 2, 8, 2)
    [void]$buttons.Controls.Add($b)
    return $b
}

function Read-Form {
    $cfg.Renderer        = $(if ($renderer.SelectedIndex -eq 0) { 'GPU' } else { 'Software' })
    $cfg.ResolutionScale = [string]($res.SelectedIndex + 1)
    $cfg.TextureFilter   = [string]$tex.SelectedIndex
    $cfg.Fullscreen      = [string]$mode.SelectedIndex
    $cfg.WindowScale     = [string]($win.SelectedIndex + 1)
    $cfg.FPSLimit        = $fpsValues[$fps.SelectedIndex]
    $cfg.VSync           = $(if ($vsync.Checked) { '1' } else { '0' })
    $cfg.Mute            = $(if ($mute.Checked) { '1' } else { '0' })
}

$cancel = New-Button 'Cancel'
$cancel.Add_Click({ $form.Close() })
$save = New-Button 'Save'
$save.Add_Click({ Read-Form; Save-Settings; $form.Close() })
$play = New-Button 'Save and Play'
$play.Add_Click({
    Read-Form; Save-Settings
    Start-Process -FilePath (Join-Path $root 'Play.cmd') -WorkingDirectory $root
    $form.Close()
})
$form.AcceptButton = $play
$form.CancelButton = $cancel

if ($env:FBOS_SETTINGS_SNAPSHOT) {     # test hook: picture of the window, then close
    $form.Add_Shown({
        $form.Refresh()
        $bmp = New-Object System.Drawing.Bitmap($form.Width, $form.Height)
        $form.DrawToBitmap($bmp, (New-Object System.Drawing.Rectangle(0, 0, $form.Width, $form.Height)))
        $bmp.Save($env:FBOS_SETTINGS_SNAPSHOT)
        $form.Close()
    })
}
[void]$form.ShowDialog()
