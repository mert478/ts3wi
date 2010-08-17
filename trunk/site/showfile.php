<?php
$name=$_REQUEST['name'];
$imagetype = exif_imagetype("../icons/".$name);
$mime=image_type_to_mime_type($imagetype);
header('Content-type: '.$mime);
echo file_get_contents('../icons/'.$name);
?>