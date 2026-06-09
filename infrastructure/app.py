#!/usr/bin/env python3
import aws_cdk as cdk
from stack import VoxIQStack

app = cdk.App()
VoxIQStack(app, "VoxIQStack")
app.synth()
